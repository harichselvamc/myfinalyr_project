from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
from datetime import datetime
import os
from bson import ObjectId
from PIL import Image
import base64
import io
from math import ceil

app = Flask(__name__)
app.secret_key = os.urandom(24)
bcrypt = Bcrypt(app)

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017')
db = client['ecommerce_db']
users_collection = db['users']
products_collection = db['products']
community_collection = db['community_posts']
purchases_collection = db['purchases']

# Utility function to encode image to base64
def encode_image(file_stream):
    img = Image.open(file_stream)
    img = img.convert("RGB")
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    return img_base64
# Custom Jinja2 filter for datetime formatting
@app.template_filter('datetimeformat')
def datetimeformat(value, format='%Y-%m-%d %H:%M'):
    """Format a datetime string."""
    try:
        dt = datetime.strptime(value, '%Y-%m-%dT%H:%M')
        return dt.strftime(format)
    except:
        return value
# Utility function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        if users_collection.find_one({"email": email}):
            flash("Email already registered. Please log in.", "warning")
            return redirect(url_for('login'))

        users_collection.insert_one({"username": username, "email": email, "password": hashed_password})
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = users_collection.find_one({"email": email})

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            flash(f"Welcome, {user['username']}!", "success")
            return redirect(url_for('products'))
        else:
            flash("Invalid email or password.", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('home'))

@app.route('/products', methods=['GET', 'POST'])
def products():
    if 'user_id' not in session:
        flash("Please log in to access this page.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        place = request.form['place']
        file = request.files.get('file')
        category = "under processing category"

        # Retrieve the owner's email from the session
        user = users_collection.find_one({"_id": ObjectId(session['user_id'])})
        owner_email = user.get('email', 'No Email Available')

        product_data = {
            "name": name,
            "price": price,
            "place": place,
            "owner_id": session['user_id'],
            "owner_name": session['username'],
            "owner_email": owner_email,  # Store the owner's email
            "category": category
        }

        if file and allowed_file(file.filename):
            product_data["image"] = encode_image(file.stream)

        products_collection.insert_one(product_data)
        flash("Product uploaded successfully!", "success")
        return redirect(url_for('products'))

    # Fetch all products from the database
    products = list(products_collection.find())
    for product in products:
        product['_id'] = str(product['_id'])
        if 'image' in product:
            product['image'] = f"data:image/jpeg;base64,{product['image']}"

    return render_template('products.html', products=products)

@app.route('/edit_product/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})

    if product['owner_id'] != session.get('user_id'):
        flash("You can only edit your own products.", "danger")
        return redirect(url_for('products'))

    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        place = request.form['place']
        category = request.form['category']
        file = request.files.get('file')

        update_data = {"name": name, "price": price, "place": place, "category": category}
        if file and allowed_file(file.filename):
            update_data["image"] = encode_image(file.stream)

        products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
        flash("Product updated successfully!", "success")
        return redirect(url_for('products'))

    product['_id'] = str(product['_id'])
    return render_template('edit_product.html', product=product)

@app.route('/delete_product/<product_id>', methods=['POST'])
def delete_product(product_id):
    product = products_collection.find_one({"_id": ObjectId(product_id)})

    if product['owner_id'] != session.get('user_id'):
        flash("You can only delete your own products.", "danger")
        return redirect(url_for('products'))

    products_collection.delete_one({"_id": ObjectId(product_id)})
    flash("Product deleted successfully!", "success")
    return redirect(url_for('products'))

@app.route('/community', methods=['GET', 'POST'])
def community():
    if 'user_id' not in session:
        flash("Please log in to access the community page.", "warning")
        return redirect(url_for('login'))

    if request.method == 'POST':
        event_name = request.form['event_name']
        place = request.form['place']
        time = request.form['time']
        description = request.form['description']
        files = request.files.getlist('images')

        post_data = {
            "event_name": event_name,
            "place": place,
            "time": time,
            "description": description,
            "timestamp": datetime.utcnow(),
            "user_id": session['user_id'],
            "username": session['username']
        }

        images_encoded = [encode_image(file.stream) for file in files if allowed_file(file.filename)]
        if images_encoded:
            post_data["images"] = images_encoded

        community_collection.insert_one(post_data)
        flash("Event posted successfully!", "success")
        return redirect(url_for('community'))

    # Handle pagination
    page = int(request.args.get('page', 1))
    per_page = 6  # Number of posts per page
    total_posts = community_collection.count_documents({})  # Total number of posts
    total_pages = ceil(total_posts / per_page)  # Calculate total pages

    # Fetch posts for the current page
    posts = list(
        community_collection.find()
        .sort("timestamp", -1)
        .skip((page - 1) * per_page)
        .limit(per_page)
    )

    for post in posts:
        post['_id'] = str(post['_id'])
        if 'images' in post:
            post['images'] = ["data:image/jpeg;base64," + img for img in post['images']]

    # Pass all necessary variables to the template
    return render_template(
        'community.html',
        posts=posts,
        page=page,
        total_pages=total_pages
    )

@app.route('/edit_community/<post_id>', methods=['GET', 'POST'])
def edit_community(post_id):
    post = community_collection.find_one({"_id": ObjectId(post_id)})

    if post['user_id'] != session.get('user_id'):
        flash("You can only edit your own posts.", "danger")
        return redirect(url_for('community'))

    if request.method == 'POST':
        event_name = request.form['event_name']
        place = request.form['place']
        time = request.form['time']
        description = request.form['description']
        files = request.files.getlist('images')

        update_data = {"event_name": event_name, "place": place, "time": time, "description": description}
        if files:
            images_encoded = [encode_image(file.stream) for file in files]
            update_data["images"] = images_encoded

        community_collection.update_one({"_id": ObjectId(post_id)}, {"$set": update_data})
        flash("Post updated successfully!", "success")
        return redirect(url_for('community'))

    post['_id'] = str(post['_id'])
    return render_template('edit_community.html', post=post)

@app.route('/delete_community/<post_id>', methods=['POST'])
def delete_community(post_id):
    post = community_collection.find_one({"_id": ObjectId(post_id)})

    if post['user_id'] != session.get('user_id'):
        flash("You can only delete your own posts.", "danger")
        return redirect(url_for('community'))

    community_collection.delete_one({"_id": ObjectId(post_id)})
    flash("Post deleted successfully!", "success")
    return redirect(url_for('community'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
