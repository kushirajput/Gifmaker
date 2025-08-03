from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from PIL import Image
import io
import os
import tempfile
import logging
from pathlib import Path
import traceback
from typing import Optional
from rembg import remove, new_session

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Photo to GIF Converter")

# Create temp directory for processed files
TEMP_DIR = Path(tempfile.gettempdir()) / "gif_converter"
TEMP_DIR.mkdir(exist_ok=True)

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Initialize rembg session for better performance
try:
    rembg_session = new_session('u2net')
    logger.info("Background removal model loaded successfully")
except Exception as e:
    logger.warning(f"Could not load background removal model: {e}")
    rembg_session = None

class ConversionError(Exception):
    """Custom exception for conversion errors"""
    pass

def validate_image_file(file: UploadFile) -> None:
    """Validate uploaded image file"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file format. Supported formats: {', '.join(SUPPORTED_FORMATS)}"
        )
    
    # Check file size (approximate, since we haven't read the full content yet)
    if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413, 
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

def remove_background(image_data: bytes) -> bytes:
    """Remove background from image using AI"""
    try:
        if rembg_session is None:
            raise ConversionError("Background removal service not available")
        
        # Remove background
        output_data = remove(image_data, session=rembg_session)
        logger.info("Background removed successfully")
        return output_data
        
    except Exception as e:
        logger.error(f"Background removal error: {str(e)}")
        raise ConversionError(f"Failed to remove background: {str(e)}")

def convert_to_gif(image_data: bytes, filename: str) -> str:
    """Remove background and convert image to transparent GIF"""
    try:
        # Remove background first
        bg_removed_data = remove_background(image_data)
        
        # Open the image with removed background
        with Image.open(io.BytesIO(bg_removed_data)) as img:
            # Ensure image has transparency
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Create output filename
            base_name = Path(filename).stem
            output_filename = f"{base_name}_no_bg.gif"
            output_path = TEMP_DIR / output_filename
            
            # Save as GIF with transparency
            img.save(
                output_path, 
                format='GIF', 
                transparency=0,
                optimize=True,
                save_all=True
            )
            
            logger.info(f"Successfully converted {filename} to transparent GIF: {output_filename}")
            return str(output_path)
            
    except ConversionError:
        # Re-raise conversion errors
        raise
    except Exception as e:
        logger.error(f"Conversion error for {filename}: {str(e)}")
        raise ConversionError(f"Failed to convert image: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def get_upload_page():
    """Serve the main upload page"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Photo to GIF Converter</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .info-box {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin-bottom: 30px;
                text-align: center;
            }
            .info-box h3 {
                margin-top: 0;
                margin-bottom: 15px;
            }
            .info-box p {
                margin: 5px 0;
                font-size: 14px;
            }
            h1 {
                color: #333;
                text-align: center;
                margin-bottom: 30px;
            }
            .upload-area {
                border: 2px dashed #ddd;
                border-radius: 10px;
                padding: 40px;
                text-align: center;
                margin-bottom: 20px;
                transition: border-color 0.3s;
            }
            .upload-area:hover {
                border-color: #007bff;
            }
            .upload-area.dragover {
                border-color: #007bff;
                background-color: #f8f9fa;
            }
            input[type="file"] {
                display: none;
            }
            .upload-btn {
                background-color: #007bff;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                margin: 10px;
            }
            .upload-btn:hover {
                background-color: #0056b3;
            }
            .convert-btn {
                background-color: #28a745;
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 5px;
                cursor: pointer;
                font-size: 16px;
                width: 100%;
                margin-top: 20px;
            }
            .convert-btn:hover {
                background-color: #218838;
            }
            .convert-btn:disabled {
                background-color: #6c757d;
                cursor: not-allowed;
            }
            .error {
                color: #dc3545;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                padding: 12px;
                border-radius: 5px;
                margin: 10px 0;
            }
            .success {
                color: #155724;
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
                padding: 12px;
                border-radius: 5px;
                margin: 10px 0;
            }
            .file-info {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }
            .loading {
                display: none;
                text-align: center;
                margin: 20px 0;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 2s linear infinite;
                margin: 0 auto;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .supported-formats {
                font-size: 14px;
                color: #666;
                margin-top: 10px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎭 Photo to Transparent GIF Converter</h1>
            
            <div class="info-box">
                <h3>✨ What this does:</h3>
                <p>• Automatically removes background from your photos using AI</p>
                <p>• Converts the result to a transparent GIF</p>
                <p>• Perfect for logos, stickers, and overlays!</p>
            </div>
            
            <div class="upload-area" id="uploadArea">
                <p>🎭 Drag and drop your image here or</p>
                <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                    Choose Photo
                </button>
                <input type="file" id="fileInput" accept=".jpg,.jpeg,.png,.bmp,.tiff,.webp" onchange="handleFileSelect(event)">
                <div class="supported-formats">
                    Supported formats: JPG, PNG, BMP, TIFF, WebP (Max: 10MB)<br>
                    <strong>✨ Background will be automatically removed!</strong>
                </div>
            </div>
            
            <div id="fileInfo" class="file-info" style="display: none;">
                <strong>Selected file:</strong> <span id="fileName"></span><br>
                <strong>Size:</strong> <span id="fileSize"></span>
            </div>
            
            <div id="errorMessage" class="error" style="display: none;"></div>
            <div id="successMessage" class="success" style="display: none;"></div>
            
            <div class="loading" id="loading">
                <div class="spinner"></div>
                <p>🎭 Removing background and converting to transparent GIF...</p>
                <small>This may take 10-30 seconds depending on image complexity</small>
            </div>
            
            <button id="convertBtn" class="convert-btn" onclick="convertToGif()" disabled>
                🎭 Remove Background & Convert to GIF
            </button>
        </div>

        <script>
            let selectedFile = null;

            // Drag and drop functionality
            const uploadArea = document.getElementById('uploadArea');
            
            ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, preventDefaults, false);
            });

            function preventDefaults(e) {
                e.preventDefault();
                e.stopPropagation();
            }

            ['dragenter', 'dragover'].forEach(eventName => {
                uploadArea.addEventListener(eventName, highlight, false);
            });

            ['dragleave', 'drop'].forEach(eventName => {
                uploadArea.addEventListener(eventName, unhighlight, false);
            });

            function highlight(e) {
                uploadArea.classList.add('dragover');
            }

            function unhighlight(e) {
                uploadArea.classList.remove('dragover');
            }

            uploadArea.addEventListener('drop', handleDrop, false);

            function handleDrop(e) {
                const dt = e.dataTransfer;
                const files = dt.files;
                if (files.length > 0) {
                    handleFile(files[0]);
                }
            }

            function handleFileSelect(event) {
                const file = event.target.files[0];
                if (file) {
                    handleFile(file);
                }
            }

            function handleFile(file) {
                // Validate file
                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff', 'image/webp'];
                const maxSize = 10 * 1024 * 1024; // 10MB

                hideMessages();

                if (!allowedTypes.includes(file.type)) {
                    showError('Please select a valid image file (JPG, PNG, BMP, TIFF, WebP)');
                    return;
                }

                if (file.size > maxSize) {
                    showError('File size must be less than 10MB');
                    return;
                }

                selectedFile = file;
                
                // Show file info
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('fileSize').textContent = formatFileSize(file.size);
                document.getElementById('fileInfo').style.display = 'block';
                document.getElementById('convertBtn').disabled = false;
                
                showSuccess('📸 Image ready! Background will be automatically removed during conversion.');
            }

            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB', 'GB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }

            async function convertToGif() {
                if (!selectedFile) {
                    showError('Please select a file first');
                    return;
                }

                hideMessages();
                showLoading(true);
                document.getElementById('convertBtn').disabled = true;

                const formData = new FormData();
                formData.append('file', selectedFile);

                try {
                    const response = await fetch('/convert', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.detail || 'Conversion failed');
                    }

                    // Get the filename from the response headers or create one
                    const contentDisposition = response.headers.get('content-disposition');
                    let filename = 'converted.gif';
                    if (contentDisposition) {
                        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                        if (filenameMatch) {
                            filename = filenameMatch[1];
                        }
                    }

                    // Create download link
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.style.display = 'none';
                    a.href = url;
                    a.download = filename;
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    document.body.removeChild(a);

                    showSuccess('✅ Successfully created transparent GIF! Download started automatically.');

                } catch (error) {
                    if (error.message.includes('Background removal service not available')) {
                        showError('❌ Background removal service is not available. Please try again later.');
                    } else if (error.message.includes('Failed to remove background')) {
                        showError('❌ Could not remove background from this image. Try a different photo with clearer subjects.');
                    } else {
                        showError('❌ ' + error.message);
                    }
                } finally {
                    showLoading(false);
                    document.getElementById('convertBtn').disabled = false;
                }
            }

            function showError(message) {
                const errorEl = document.getElementById('errorMessage');
                errorEl.textContent = message;
                errorEl.style.display = 'block';
            }

            function showSuccess(message) {
                const successEl = document.getElementById('successMessage');
                successEl.textContent = message;
                successEl.style.display = 'block';
            }

            function hideMessages() {
                document.getElementById('errorMessage').style.display = 'none';
                document.getElementById('successMessage').style.display = 'none';
            }

            function showLoading(show) {
                document.getElementById('loading').style.display = show ? 'block' : 'none';
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/convert")
async def convert_photo_to_gif(file: UploadFile = File(...)):
    """Convert uploaded photo to GIF"""
    try:
        # Validate file
        validate_image_file(file)
        
        # Read file content
        file_content = await file.read()
        
        # Check actual file size
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate that it's actually an image
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                # Just verify it can be opened
                pass
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid image file")
        
        # Convert to GIF
        output_path = convert_to_gif(file_content, file.filename)
        
        # Generate response filename
        base_name = Path(file.filename).stem
        response_filename = f"{base_name}_no_bg.gif"
        
        return FileResponse(
            path=output_path,
            filename=response_filename,
            media_type='image/gif'
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except ConversionError as e:
        logger.error(f"Conversion error: {str(e)}")
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error occurred")
    finally:
        # Reset file pointer for potential cleanup
        if hasattr(file, 'file'):
            try:
                file.file.seek(0)
            except:
                pass

@app.on_event("startup")
async def startup_event():
    """Cleanup old temporary files on startup"""
    try:
        for file_path in TEMP_DIR.glob("*.gif"):
            if file_path.is_file():
                file_path.unlink()
        logger.info("Cleaned up temporary files")
    except Exception as e:
        logger.warning(f"Could not clean up temp files: {e}")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {str(exc)}\n{traceback.format_exc()}")
    return HTTPException(status_code=500, detail="An unexpected error occurred")

if __name__ == "__main__":
    print("🎭 Starting Photo to Transparent GIF Converter...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🎨 Features: AI Background Removal + Transparent GIF Export")
    print("📁 Supported formats: JPG, PNG, BMP, TIFF, WebP (Max: 10MB)")
    print("⚠️  First conversion may be slower while loading AI model...")
    

port = int(os.environ.get("PORT", 8000))

uvicorn.run(
    app,
    host="0.0.0.0",
    port=port,
    log_level="info"
)
