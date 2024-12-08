from flask import Flask, render_template, Response, request, jsonify, url_for, redirect
from dotenv import load_dotenv
import os
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
import io
import json
from datetime import datetime
import threading
import base64
import requests

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Ensure upload directory exists
UPLOAD_FOLDER = Path(app.static_folder or '.') / 'uploads'
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Social media credentials
FACEBOOK_APP_ID = os.getenv('FACEBOOK_APP_ID', '')
FACEBOOK_APP_SECRET = os.getenv('FACEBOOK_APP_SECRET', '')
INSTAGRAM_BUSINESS_ACCOUNT_ID = os.getenv('INSTAGRAM_BUSINESS_ACCOUNT_ID', '')
INSTAGRAM_ACCESS_TOKEN = os.getenv('INSTAGRAM_ACCESS_TOKEN', '')

# Try multiple potential paths for Haar cascade
HAAR_CASCADE_PATHS = [
    '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
    '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
    '/usr/local/share/OpenCV/haarcascades/haarcascade_frontalface_default.xml'
]

# Find the first existing Haar cascade file
FACE_CASCADE_PATH = next((path for path in HAAR_CASCADE_PATHS if os.path.exists(path)), None)

if FACE_CASCADE_PATH is None:
    raise FileNotFoundError("Could not find Haar cascade file for face detection. Please install OpenCV properly.")

# Initialize face detection
face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)

# Global variables for camera control
camera = None
camera_active = False
camera_lock = threading.Lock()
frame_skip = 2  # Process every nth frame
frame_count = 0

def analyze_face(face_img):
    """Advanced face analysis with robust error handling"""
    try:
        # Resize and preprocess
        face_img = cv2.resize(face_img, (128, 128))
        gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(face_img, cv2.COLOR_BGR2HSV)
        
        # Compute features
        brightness = np.mean(gray)
        hue = np.mean(hsv[:,:,0])
        saturation = np.mean(hsv[:,:,1])
        
        # Skin tone classification
        skin_tones = {
            (0, 85): 'dark',
            (85, 170): 'medium',
            (170, 255): 'light'
        }
        skin_tone = next((tone for (low, high), tone in skin_tones.items() 
                          if low <= brightness < high), 'medium')
        
        # Hair color classification
        hair_colors = {
            (0, 20): 'black',
            (20, 40): 'brown',
            (40, 60): 'dark brown',
            (60, 100): 'light brown',
            (100, 255): 'blonde'
        }
        hair_color = next((color for (low, high), color in hair_colors.items() 
                           if low <= hue < high), 'brown')
        
        # Eye color estimation (very basic)
        eye_colors = {
            (0, 50): 'dark brown',
            (50, 100): 'brown',
            (100, 150): 'hazel',
            (150, 255): 'blue/green'
        }
        eye_color = next((color for (low, high), color in eye_colors.items() 
                          if low <= saturation < high), 'brown')
        
        return {
            'description': f'Person with {skin_tone} skin, {hair_color} hair',
            'details': {
                'skin_tone': skin_tone,
                'hair': {
                    'color': hair_color,
                    'style': 'natural'
                },
                'eyes': {
                    'color': eye_color
                },
                'confidence': min(max(brightness / 255, 0.5), 0.9)
            }
        }
    except Exception as e:
        print(f"Face analysis error: {e}")
        return {
            'description': 'Unidentified person',
            'details': {
                'skin_tone': 'unknown',
                'hair': {
                    'color': 'unknown',
                    'style': 'unknown'
                },
                'eyes': {
                    'color': 'unknown'
                },
                'confidence': 0.5
            }
        }

def analyze_scene(image):
    """Comprehensive scene analysis"""
    try:
        # Resize for efficiency
        image = cv2.resize(image, (256, 256))
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Lighting and scene characteristics
        brightness = np.mean(gray)
        contrast = np.std(gray)
        
        # Lighting classification
        if brightness < 85:
            lighting = 'dark'
        elif brightness < 170:
            lighting = 'moderate'
        else:
            lighting = 'bright'
        
        # Scene type estimation (very basic)
        scene_types = {
            'indoor': brightness < 150 and contrast < 50,
            'outdoor': brightness > 180 and contrast > 60,
            'neutral': True
        }
        scene_type = next((scene for scene, condition in scene_types.items() if condition), 'neutral')
        
        return {
            'description': f'A {lighting} {scene_type} scene',
            'lighting': lighting,
            'scene_type': scene_type,
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        print(f"Scene analysis error: {e}")
        return {
            'description': 'Unable to analyze scene',
            'lighting': 'unknown',
            'scene_type': 'unknown',
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                   mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/toggle_camera', methods=['POST'])
def toggle_camera():
    global camera, camera_active
    
    try:
        with camera_lock:
            camera_active = not camera_active
            
            if camera_active:
                if camera is None:
                    camera = cv2.VideoCapture(0)
                    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    camera.set(cv2.CAP_PROP_FPS, 15)  # Lower FPS
                    
                    if not camera.isOpened():
                        camera = None
                        camera_active = False
                        return jsonify({'camera_active': False, 'error': 'Failed to open camera'})
            else:
                if camera is not None:
                    camera.release()
                    camera = None
        
        return jsonify({'camera_active': camera_active})
    except Exception as e:
        print(f"Camera error: {str(e)}")
        return jsonify({'camera_active': False, 'error': str(e)}), 500

def gen_frames():
    global camera, camera_active, frame_count
    while True:
        with camera_lock:
            if not camera_active or camera is None:
                break
            
            success, frame = camera.read()
            if not success:
                break
            
            # Skip frames to reduce processing
            frame_count += 1
            if frame_count % frame_skip != 0:
                continue
            
            # Resize frame to reduce processing
            frame = cv2.resize(frame, (640, 480))
            
            # Detect faces
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            # Draw rectangles around faces
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame = buffer.tobytes()
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    global camera
    with camera_lock:
        if camera is None or not camera_active:
            return jsonify({'error': 'Camera is not active'}), 400
        
        success, frame = camera.read()
        if not success:
            return jsonify({'error': 'Failed to capture frame'}), 500
        
        filename = save_snapshot(frame)
        scene_info = analyze_scene(frame)
        
        return jsonify({
            'filename': filename,
            'url': url_for('static', filename=filename.split('static/')[1]),
            'analysis': scene_info
        })

@app.route('/get_snapshots')
def get_snapshots():
    snapshots = []
    for file in Path(UPLOAD_FOLDER).glob('*.jpg'):
        snapshots.append({
            'filename': file.name,
            'url': url_for('static', filename=f'uploads/{file.name}'),
            'timestamp': datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        })
    return jsonify(snapshots)

@app.route('/share', methods=['POST'])
def share():
    data = request.json or {}
    platform = data.get('platform', '')
    image_url = data.get('image_url', '')
    caption = data.get('caption', '')
    
    if not platform or not image_url:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        if platform == 'facebook':
            # Initialize Facebook Graph API
            graph = facebook.GraphAPI(access_token=str(FACEBOOK_APP_SECRET or ''))
            
            # Get the full path of the image
            image_path = Path(app.root_path) / str(image_url).lstrip('/')
            
            # Post to Facebook
            with open(image_path, 'rb') as image:
                graph.put_photo(image=image, message=caption)
            
            return jsonify({'message': 'Shared to Facebook successfully'})
            
        elif platform == 'instagram':
            # Instagram Graph API endpoint
            endpoint = f"https://graph.facebook.com/v13.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID or ''}/media"
            
            # Get the full URL for the image
            image_full_url = request.host_url.rstrip('/') + str(image_url)
            
            # Create container for Instagram
            params = {
                'image_url': image_full_url,
                'caption': caption,
                'access_token': str(INSTAGRAM_ACCESS_TOKEN or '')
            }
            
            # Create container
            response = requests.post(endpoint, params=params)
            result = response.json()
            
            if 'id' in result:
                # Publish the container
                publish_endpoint = f"https://graph.facebook.com/v13.0/{INSTAGRAM_BUSINESS_ACCOUNT_ID or ''}/media_publish"
                publish_params = {
                    'creation_id': result['id'],
                    'access_token': str(INSTAGRAM_ACCESS_TOKEN or '')
                }
                publish_response = requests.post(publish_endpoint, params=publish_params)
                
                if publish_response.status_code == 200:
                    return jsonify({'message': 'Shared to Instagram successfully'})
            
            return jsonify({'error': 'Failed to share to Instagram'}), 500
        else:
            return jsonify({'error': 'Unsupported platform'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analyze_frame', methods=['GET'])
def analyze_frame():
    global camera
    with camera_lock:
        if camera is None or not camera_active:
            return jsonify({
                'faces': [],
                'background': {
                    'lighting': 'unknown',
                    'description': 'Camera is not active',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            })
        
        success, frame = camera.read()
        if not success:
            return jsonify({
                'faces': [],
                'background': {
                    'lighting': 'unknown',
                    'description': 'Failed to capture frame',
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
            })
        
        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        # Analyze faces
        face_details = []
        for (x, y, w, h) in faces:
            face_img = frame[y:y+h, x:x+w]
            face_analysis = analyze_face(face_img)
            face_details.append({
                'location': {
                    'x': int(x), 
                    'y': int(y), 
                    'width': int(w), 
                    'height': int(h)
                },
                'details': face_analysis
            })
        
        # Analyze scene
        scene_info = analyze_scene(frame)
        
        return jsonify({
            'faces': face_details,
            'background': scene_info
        })

@app.route('/analyze_image', methods=['POST'])
def analyze_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Ensure UPLOAD_FOLDER is a valid path
        upload_path = Path(UPLOAD_FOLDER or '.')
        upload_path.mkdir(parents=True, exist_ok=True)
        
        # Save uploaded file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = upload_path / f'upload_{timestamp}.jpg'
        file.save(str(filename))
        
        # Read image
        image = cv2.imread(str(filename))
        if image is None:
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Detect faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        # Analyze faces
        face_details = []
        for (x, y, w, h) in faces:
            face_img = image[y:y+h, x:x+w]
            face_analysis = analyze_face(face_img)
            face_details.append({
                'location': {
                    'x': int(x), 
                    'y': int(y), 
                    'width': int(w), 
                    'height': int(h)
                },
                'details': face_analysis
            })
            
        # Analyze scene
        scene_info = analyze_scene(image)
        
        # Construct response
        return jsonify({
            'faces': face_details,
            'background': scene_info,
            'image_path': str(filename).replace(str(app.static_folder or '.'), 'static')
        })
    
    except Exception as e:
        print(f"Image analysis error: {e}")
        return jsonify({'error': 'Failed to process image'}), 500

@app.route('/analyze_upload', methods=['POST'])
def analyze_upload():
    """Analyze an uploaded image"""
    if 'image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    try:
        # Read image
        image_bytes = file.read()
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        # Detect faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Prepare response
        response_data = {
            'faces': [],
            'background': {}
        }
        
        # Analyze faces
        for (x, y, w, h) in faces[:1]:  # Limit to first face
            face_roi = image[y:y+h, x:x+w]
            face_analysis = analyze_face(face_roi)
            response_data['faces'].append({
                'location': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                'details': face_analysis
            })
        
        # Scene analysis
        response_data['background'] = analyze_scene(image)
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Upload analysis error: {e}")
        return jsonify({'error': 'Failed to analyze image'}), 500

@app.route('/analyze_webcam', methods=['POST'])
def analyze_webcam():
    """Analyze a webcam snapshot"""
    if 'image' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['image']
    
    try:
        # Read image
        image_bytes = file.read()
        image_array = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        
        # Detect faces
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        # Prepare response
        response_data = {
            'faces': [],
            'background': {}
        }
        
        # Analyze faces
        for (x, y, w, h) in faces[:1]:  # Limit to first face
            face_roi = image[y:y+h, x:x+w]
            face_analysis = analyze_face(face_roi)
            response_data['faces'].append({
                'location': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                'details': face_analysis
            })
        
        # Scene analysis
        response_data['background'] = analyze_scene(image)
        
        return jsonify(response_data)
    
    except Exception as e:
        print(f"Webcam analysis error: {e}")
        return jsonify({'error': 'Failed to analyze image'}), 500

def save_snapshot(frame):
    """Save a snapshot to the uploads directory"""
    # Ensure UPLOAD_FOLDER is a valid path
    upload_path = Path(UPLOAD_FOLDER or '.')
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Resize image before saving to reduce file size
    frame = cv2.resize(frame, (640, 480))
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'snapshot_{timestamp}.jpg'
    filepath = upload_path / filename
    
    cv2.imwrite(str(filepath), frame)
    return f'static/uploads/{filename}'

if __name__ == '__main__':
    app.run(debug=True)
