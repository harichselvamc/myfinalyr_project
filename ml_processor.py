from pymongo import MongoClient
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from PIL import Image
import numpy as np
import base64
import io

# Define the class names (ensure these are in the same order as during training)
class_names = ['organic', 'recycle']  # Replace with your actual class names

# Load the trained model
model_path = 'model_small.h5'
model = load_model(model_path)

# MongoDB connection
client = MongoClient('mongodb://localhost:27017')
db = client['product_db']
collection = db['products']

def preprocess_image(img: Image.Image, img_width: int, img_height: int):
    """Preprocess the image for model prediction."""
    img = img.resize((img_width, img_height))
    img_array = image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0
    return img_array

def predict_image(img_array):
    """Predict the class of the image."""
    prediction = model.predict(img_array)
    predicted_class_index = np.argmax(prediction)
    predicted_class = class_names[predicted_class_index]
    return predicted_class

def update_product_category(product_id, category):
    """Update the product category in MongoDB."""
    result = collection.update_one({"_id": product_id}, {"$set": {"category": category}})
    if result.modified_count > 0:
        print(f"Product ID {product_id} updated with category '{category}'")
    else:
        print(f"Product ID {product_id} not updated")

def process_and_update_products():
    """Retrieve products from MongoDB, process images, and update categories."""
    products = collection.find()
    
    for product in products:
        if 'image' in product:
            try:
                # Decode the base64 image
                img_data = base64.b64decode(product['image'])
                img = Image.open(io.BytesIO(img_data))
                img = img.convert("RGB")

                # Preprocess the image and make a prediction
                img_array = preprocess_image(img, img_width=80, img_height=45)  # Ensure these match your model's input size
                predicted_class = predict_image(img_array)
                
                # Update MongoDB with the predicted category
                update_product_category(product['_id'], predicted_class)

            except Exception as e:
                print(f"Error processing product ID {product['_id']}: {e}")

if __name__ == '__main__':
    process_and_update_products()
