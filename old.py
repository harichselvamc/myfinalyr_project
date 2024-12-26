from flask import Flask, request, jsonify, render_template, redirect, url_for
from pymongo import MongoClient
from PIL import Image
import base64
import io
import os
from bson import ObjectId
from datetime import datetime
from math import ceil

app = Flask(__name__)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017')
db = client['ecommerce_db']  # Updated database name
products_collection = db['products']
community_collection = db['community_posts']

# Removed DEFAULT_CATEGORY as it's no longer needed in community_posts
# DEFAULT_CATEGORY = 'undefined'  

# Utility function to encode image to base64
def encode_image(file_stream):
    img = Image.open(file_stream)
    img = img.convert("RGB")
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_base64

# Utility function to check allowed file extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Context processor to inject current year into all templates
@app.context_processor
def inject_current_year():
    return {'current_year': datetime.utcnow().year}

# Custom Jinja2 filter for datetime formatting
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    """Format a datetime string."""
    try:
        dt = datetime.strptime(value, '%Y-%m-%dT%H:%M')
        return dt.strftime(format)
    except:
        return value

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/community', methods=['GET', 'POST'])
def community():
    if request.method == 'POST':
        try:
            event_name = request.form['event_name']
            place = request.form['place']
            time = request.form['time']
            description = request.form['description']
            files = request.files.getlist('images')  # Handle multiple images

            post_data = {
                "event_name": event_name,
                "place": place,
                "time": time,  # Stored as string; consider parsing to datetime if needed
                "description": description,
                "timestamp": datetime.utcnow()
            }

            images_encoded = []
            for file in files:
                if file and allowed_file(file.filename):
                    images_encoded.append(encode_image(file.stream))
            
            if images_encoded:
                post_data["images"] = images_encoded

            community_collection.insert_one(post_data)
            return redirect(url_for('community'))
        except Exception as e:
            return f"An error occurred: {e}", 422

    # GET request with optional pagination
    page = int(request.args.get('page', 1))
    per_page = 6  # Number of posts per page

    total_posts = community_collection.count_documents({})
    total_pages = ceil(total_posts / per_page)
    
    posts_cursor = community_collection.find().sort("timestamp", -1).skip((page - 1) * per_page).limit(per_page)
    posts = list(posts_cursor)
    
    for post in posts:
        post['_id'] = str(post['_id'])
        if 'images' in post:
            post['images'] = ["data:image/jpeg;base64," + img for img in post['images']]
    
    return render_template('community.html', posts=posts, page=page, total_pages=total_pages)

@app.route('/products', methods=['GET', 'POST'])
def products():
    if request.method == 'POST':
        try:
            name = request.form['name']
            price = float(request.form['price'])
            place = request.form['place']
            # Removed category input from form; set to 'undefined' by default
            category = 'under processing category'
            file = request.files.get('file')

            product_data = {
                "name": name,
                "price": price,
                "place": place,
                "category": category  # Set to 'undefined' by default
            }

            if file and allowed_file(file.filename):
                product_data["image"] = encode_image(file.stream)

            products_collection.insert_one(product_data)
            return redirect(url_for('products'))
        except Exception as e:
            return f"An error occurred: {e}", 422

    # GET request with optional filtering
    category_filter = request.args.get('category', None)
    if category_filter:
        query = {"category": category_filter}
    else:
        query = {}

    products = list(products_collection.find(query))
    for product in products:
        product['_id'] = str(product['_id'])
        if 'image' in product:
            product['image'] = "data:image/jpeg;base64," + product['image']
    # Since all categories are 'undefined', this part might be redundant
    # But keeping it for possible future categories
    categories = products_collection.distinct('category')
    return render_template('products.html', products=products, categories=categories, selected_category=category_filter)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
