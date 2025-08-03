from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn
from PIL import Image
import io
import os
import tempfile
import logging
from pathlib import Path
from rembg import remove

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Photo to GIF Converter")

# Supported formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Serve the main upload page"""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Photo to GIF Converter</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
            }
            .container {
                background: rgba(255, 255, 255, 0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            h1 { text-align: center; color: #2c3e50; margin-bottom: 30px; }
            .upload-area {
                border: 3px dashed #bdc3c7;
                border-radius: 15px;
                padding: 40px;
                text-align: center;
                margin: 30px 0;
                transition: all 0.3s ease;
            }
            .upload-area:hover {
                border-color: #3498db;
                background: rgba(52, 152, 219, 0.1);
            }
            .btn {
                background: linear-gradient(135deg, #3498db, #2980b9);
                color: white;
                padding: 15px 30px;
                border: none;
                border-radius: 25px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s ease;
            }
            .btn:hover { transform: translateY(-2px); }
            .btn:disabled { background: #95a5a6; cursor: not-allowed; }
            .convert-btn {
                background: linear-gradient(135deg, #2ecc71, #27ae60);
                width: 100%;
                margin-top: 20px;
            }
            .file-info {
                background: rgba(52, 152, 219, 0.1);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                display: none;
            }
            .message {
                padding: 15px;
                border-radius: 10px;
                margin: 15px 0;
                display: none;
            }
            .error { background: rgba(231, 76, 60, 0.1); color: #e74c3c; }
            .success { background: rgba(46, 204, 113, 0.1); color: #27ae60; }
            input[type="file"] { display: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎭 Photo to Transparent GIF</h1>
            <p style="text-align: center; color: #7f8c8d;">Upload a photo → AI removes background → Download transparent GIF</p>
            
            <div class="upload-area">
                <p>📸 Click to select your photo</p>
                <button class="btn" onclick="document.getElementById('fileInput').click()">
                    Choose Photo
                </button>
                <input type="file" id="fileInput" accept=".jpg,.jpeg,.png,.bmp,.tiff,.webp" onchange="handleFile(event)">
                <p style="font-size: 0.9em; color: #7f8c8d; margin-top: 15px;">
                    JPG, PNG, BMP, TIFF, WebP • Max 10MB
                </p>
            </div>
            
            <div id="fileInfo" class="file-info">
                <strong>📄 Selected:</strong> <span id="fileName"></span><br>
                <strong>📏 Size:</strong> <span id="fileSize"></span>
            </div>
            
            <div id="errorMessage" class="message error"></div>
            <div id="successMessage" class="message success"></div>
            
            <button id="convertBtn" class="btn convert-btn" onclick="convertToGif()" disabled>
                🎭 Remove Background & Create GIF
            </button>
        </div>

        <script>
            let selectedFile = null;

            function handleFile(event) {
                const file = event.target.files[0];
                if (!file) return;

                const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/bmp', 'image/tiff', 'image/webp'];
                const maxSize = 10 * 1024 * 1024;

                hideMessages();

                if (!allowedTypes.includes(file.type)) {
                    showError('Please select a valid image file');
                    return;
                }

                if (file.size > maxSize) {
                    showError('File size must be less than 10MB');
                    return;
                }

                selectedFile = file;
                document.getElementById('fileName').textContent = file.name;
                document.getElementById('fileSize').textContent = formatFileSize(file.size);
                document.getElementById('fileInfo').style.display = 'block';
                document.getElementById('convertBtn').disabled = false;
                showSuccess('Photo ready! Click to convert.');
            }

            async function convertToGif() {
                if (!selectedFile) return;

                hideMessages();
                const btn = document.getElementById('convertBtn');
                btn.disabled = true;
                btn.textContent = '🤖 Processing...';

                const formData = new FormData();
                formData.append('file', selectedFile);

                try {
                    const response = await fetch('/convert', {
                        method: 'POST',
                        body: formData
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.detail || 'Conversion failed');
                    }

                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = selectedFile.name.replace(/\.[^/.]+$/, "") + "_no_bg.gif";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);

                    showSuccess('🎉 Success! Your GIF has been downloaded!');
                } catch (error) {
                    showError(error.message);
                } finally {
                    btn.disabled = false;
                    btn.textContent = '🎭 Remove Background & Create GIF';
                }
            }

            function formatFileSize(bytes) {
                if (bytes === 0) return '0 Bytes';
                const k = 1024;
                const sizes = ['Bytes', 'KB', 'MB'];
                const i = Math.floor(Math.log(bytes) / Math.log(k));
                return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
            }

            function showError(message) {
                const el = document.getElementById('errorMessage');
                el.textContent = '❌ ' + message;
                el.style.display = 'block';
            }

            function showSuccess(message) {
                const el = document.getElementById('successMessage');
                el.textContent = '✅ ' + message;
                el.style.display = 'block';
            }

            function hideMessages() {
                document.getElementById('errorMessage').style.display = 'none';
                document.getElementById('successMessage').style.display = 'none';
            }
        </script>
    </body>
    </html>
    """

@app.post("/convert")
async def convert_image(file: UploadFile = File(...)):
    """Convert image to transparent GIF"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in SUPPORTED_FORMATS:
            raise HTTPException(status_code=400, detail="Unsupported file format")
        
        # Read and process
        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Remove background
        output_data = remove(content)
        
        # Convert to GIF
        with Image.open(io.BytesIO(output_data)) as img:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as tmp:
                img.save(tmp.name, format='GIF', transparency=0, optimize=True)
                temp_path = tmp.name
        
        # Return file
        filename = Path(file.filename).stem + "_no_bg.gif"
        return FileResponse(temp_path, filename=filename, media_type='image/gif')
        
    except Exception as e:
        logger.error(f"Conversion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "GIF converter is running"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
