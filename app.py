from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
from datetime import datetime
from pymongo import MongoClient
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input
import logging
import cloudinary
import cloudinary.uploader

# Initialize Flask app
app = Flask(__name__)

# Enable CORS for all routes
CORS(
    app,
    origins=["https://pet-app-frontend-git-main-kr96adityas-projects.vercel.app"],  # Replace with your frontend URL
    methods=["GET", "POST", "OPTIONS"],  # Allow specific HTTP methods
    allow_headers=["Content-Type"],  # Allow specific headers
    supports_credentials=True  # Allow cookies and credentials
)

# MongoDB connection
client = MongoClient("mongodb+srv://kr96aditya:qwerty96@cluster0.dc9e2.mongodb.net/pet_app?retryWrites=true&w=majority")
db = client.pet_app
animals_collection = db.animals

# Cloudinary configuration
cloudinary.config(
    cloud_name="dawmm0hm2",
    api_key="747655647237278",
    api_secret="flJ_taFlnSi0rt0Mbs5POnEb9eA"
)

# Initialize MobileNetV2 globally
try:
    mobilenet_model = MobileNetV2(weights='imagenet', include_top=True)
except Exception as e:
    logging.error(f"Error loading MobileNetV2: {e}")
    mobilenet_model = None

def extract_features(image):
    """Extract features using MobileNetV2"""
    try:
        if image is None or mobilenet_model is None:
            return None

        # Resize and preprocess
        resized = cv2.resize(image, (224, 224))
        if len(resized.shape) == 2:  # Handle grayscale
            resized = cv2.cvtColor(resized, cv2.COLOR_GRAY2RGB)
        elif resized.shape[2] == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Extract deep features
        preprocessed = preprocess_input(np.expand_dims(resized, axis=0))
        features = mobilenet_model.predict(preprocessed, verbose=0)
        features = features.flatten()

        # Normalize
        features = features / (np.linalg.norm(features) + 1e-7)
        return features.tolist()  # Convert to list for JSON serialization

    except Exception as e:
        logging.error(f"Error in extract_features: {e}")
        return None

def compare_features(features1, features2):
    """Compare features using cosine similarity"""
    try:
        if features1 is None or features2 is None:
            return 0.0

        f1 = np.array(features1)
        f2 = np.array(features2)

        similarity = np.dot(f1, f2) / (np.linalg.norm(f1) * np.linalg.norm(f2) + 1e-7)
        return float(similarity)  # Ensure it's JSON serializable

    except Exception as e:
        logging.error(f"Error in compare_features: {e}")
        return 0.0

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'https://pet-app-frontend-git-main-kr96adityas-projects.vercel.app')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    return response

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/register', methods=['POST', 'OPTIONS'])
def register_animal():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', 'https://pet-app-frontend-git-main-kr96adityas-projects.vercel.app')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response, 200

    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        file = request.files['image']
        if not file:
            return jsonify({'success': False, 'error': 'No selected file'}), 400

        # Validate file type
        if not allowed_file(file.filename):
            return jsonify({'success': False, 'error': 'Invalid file type. Only PNG, JPG, and JPEG are allowed.'}), 400

        # Read file data
        file_data = file.read()
        if not file_data:
            return jsonify({'success': False, 'error': 'Empty file data'}), 400

        # Upload image to Cloudinary
        upload_result = cloudinary.uploader.upload(file_data, resource_type="image")
        image_url = upload_result['secure_url']

        # Decode image for feature extraction
        image = cv2.imdecode(np.frombuffer(file_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({'success': False, 'error': 'Failed to decode image'}), 400

        # Extract features
        features = extract_features(image)
        if features is None:
            return jsonify({'success': False, 'error': 'Failed to extract features'}), 400

        # Generate new animal ID
        animal_id = f"ANI{animals_collection.count_documents({}) + 1:04d}"

        # Create database entry
        entry = {
            'animal_id': animal_id,
            'image_url': image_url,
            'features': features,
            'registered_at': datetime.now().isoformat()
        }

        # Insert into MongoDB
        animals_collection.insert_one(entry)

        response = jsonify({
            'success': True,
            'animal_id': animal_id,
            'image_url': image_url,
            'registered_at': entry['registered_at']
        })
        return response

    except Exception as e:
        logging.error(f"Error in register: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/search', methods=['POST', 'OPTIONS'])
def search_animal():
    if request.method == 'OPTIONS':
        # Handle preflight request
        response = jsonify({'success': True})
        response.headers.add('Access-Control-Allow-Origin', 'https://pet-app-frontend-git-main-kr96adityas-projects.vercel.app')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response, 200

    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'}), 400

        file = request.files['image']
        if not file:
            return jsonify({'success': False, 'error': 'No selected file'}), 400

        # Read file data
        file_data = file.read()
        if not file_data:
            return jsonify({'success': False, 'error': 'Empty file data'}), 400

        # Decode image for feature extraction
        image = cv2.imdecode(np.frombuffer(file_data, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({'success': False, 'error': 'Failed to decode image'}), 400

        # Extract features
        search_features = extract_features(image)
        if search_features is None:
            return jsonify({'success': False, 'error': 'Failed to extract features'}), 400

        # Match against database
        results = []
        similarity_threshold = 0.7

        for entry in animals_collection.find():
            similarity = compare_features(search_features, entry['features'])
            if similarity > similarity_threshold:
                results.append({
                    'animal_id': entry['animal_id'],
                    'image_url': entry.get('image_url', ''),  # Use .get() to handle missing field
                    'similarity': similarity,
                    'registered_at': entry['registered_at']
                })

        # Sort results by similarity
        results = sorted(results, key=lambda x: x['similarity'], reverse=True)[:5]

        return jsonify({
            'success': True,
            'matches': results
        })

    except Exception as e:
        logging.error(f"Error in search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)