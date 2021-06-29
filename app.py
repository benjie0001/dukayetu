from flask import Flask, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_wtf import FlaskForm
from sqlalchemy.orm import backref
from werkzeug import datastructures
from wtforms import StringField, IntegerField, TextAreaField, HiddenField, SelectField #these fields corce form input to their specific data types
from flask_wtf.file import FileField, FileAllowed
import random

app = Flask(__name__)

photos = UploadSet('photos', IMAGES)

app.config['UPLOADED_PHOTOS_DEST'] = 'images'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dukayetu.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'mysecret'

configure_uploads(app, photos)


db = SQLAlchemy(app)
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('db', MigrateCommand)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    price = db.Column(db.Integer)
    stock = db.Column(db.Integer)
    description = db.Column(db.String(500))
    image = db.Column(db.String(100))
    #a backreference relationship to relay info to the order table
    orders = db.relationship('Order_Items',backref='product', lazy=True)

#table for order
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(5))
    first_name =  db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone_number = db.Column(db.Integer)
    email = db.Column(db.String(50))
    address = db.Column(db.String(50))
    city = db.Column(db.String(50))
    country = db.Column(db.String(50))
    status = db.Column(db.String(50))
    payment_type = db.Column(db.String(50))
    items = db.relationship('Order_Items',backref='order',lazy=True)#append each order item to items table
    
    #define method to get the total from the order,order_items table and join product table
    def order_total(self):
        return db.session.query(db.func.sum(Order_Items.quantity*Product.price)).join(Product).filter(Order_Items.order_id==self.id).scalar() + 10

    def quantity_total(self):
        return db.session.query(db.func.sum(Order_Items.quantity)).filter(Order_Items.order_id==self.id).scalar()
#table for items included in the order
class Order_Items(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column (db.Integer)

class AddProduct(FlaskForm):
    name = StringField('Name')
    price = IntegerField('Price')
    stock = IntegerField('Stock')
    description = TextAreaField('Description')
    image= FileField('Image', validators=[FileAllowed(IMAGES, 'Only Images are accepted')])
#add to cart functionality to connect to database using forms
class AddToCart(FlaskForm):
    quantity = IntegerField('Quantity') 
    id = HiddenField('ID')

#create form using flaskform to be filled on the checkout page and connect to database
class Checkout(FlaskForm):
    first_name = StringField('First Name')
    last_name = StringField('Last Name')
    phone_number = StringField('Number')
    email = StringField('Email')
    address = StringField('Address')
    city = SelectField('City', choices=[('Nbi','Nairobi'),('Nkr','Nakuru'),('Msa','Mombasa')])
    country = SelectField('Country',choices=[('KEN','Kenya')])
    payment_type = SelectField('Payment type',choices=[('Mpesa','Mpesa'),('credit/debit','Credit/Debit Card'),('Airtelmoney','Airtel Money Transfer'),('POD','Payment on Delivery')])
   
def handle_cart():
    products=[]
    grand_total=0
    index=0
    quanitity_total =0

    for item in session['cart']:
        product=Product.query.filter_by(id=item['id']).first()
        quantity =int(item['quantity'])
        total = quantity * product.price
        grand_total +=total
        quanitity_total +=quantity

        products.append({'id':product.id,'name':product.name,'price':product.price,'image':product.image,'quantity':quantity, 'total':total,'index':index })
        index +=1
        
        grand_total_plus_shipping = grand_total + 10

    return products,grand_total,grand_total_plus_shipping,quanitity_total



@app.route('/')
def index():#home page. shows items available in the store
    #query the database to show existing items in the database
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route('/product/<id>')
def product(id):
    product = Product.query.filter_by(id=id).first()#query database filtered by unique id
    form = AddToCart()
    return render_template('view-product.html', product=product, form =form)

@app.route('/quick-add/<id>')
def quick_add(id):
    if 'cart' not in session:
        session['cart']= []

    session['cart'].append({'id': id, 'quantity' :1})
    session.modified =True

    return redirect(url_for('index'))

@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'cart' not in session:
        session['cart'] = []#instantiate a list to hold values for product quantity and id

    form = AddToCart()

    if form.validate_on_submit(): #validates the form when submit is true
        
        #append a dictionary for product id and quantity
        session['cart'].append({'id': form.id.data, 'quantity' : form.quantity.data }) 
        session.modified = True    #calls session directly  
        
    return redirect(url_for('index'))#returns to index

@app.route('/cart')
def cart():
    products,grand_total,grand_total_plus_shipping,quantity_total=handle_cart()

    return render_template('cart.html',products=products,grand_total=grand_total,grand_total_plus_shipping=grand_total_plus_shipping,quantity_total=quantity_total)

@app.route('/remove-from-cart/<index>')
def remove_from_cart(index):
    del session['cart'][int(index)]
    session.modified=True
    return redirect(url_for('cart'))

@app.route('/checkout',methods=['GET','POST'])
def checkout(): 
    #pass form to checkout template
    form = Checkout()
    products,grand_total,grand_total_plus_shipping,quantity_total=handle_cart()
    
    if form.validate_on_submit():
        products,grand_total,grand_total_plus_shipping=handle_cart()
        order=Order()
        #use pythons populate object function to recall everything on the table order
        form.populate_obj(order)
        #random reference and status definitions
        order.reference=''.join([random.choice('ABCDE') for _ in range(10)])
        order.status='PENDING' 
        #loop over products to create order items
        
        for product in products:
            order_items=Order_Items(quantity=product['quantity'],product_id=product['id'])
            order.items.append(order_items)

            #query to update stock when item is ordered
            product = Product.query.filter_by(id=product['id']).update({'stock': Product.stock - product['quantity']})

        db.session.add(order)
        db.session.commit()

        session['cart'] = []#clears out cart # remember to make changes on it
        session.modified = True

        return redirect (url_for('index'))#remember to create a confirm checkout template

                    
    return render_template('checkout.html',form=form, products=products,grand_total=grand_total,grand_total_plus_shipping=grand_total_plus_shipping,quantity_total=quantity_total)

@app.route('/admin')
def admin():
    products = Product.query.all()
    products_in_stock = Product.query.filter(Product.stock>0).count()
    
    #query for order made
    orders = Order.query.all()
    return render_template('admin/index.html', admin=True, products=products, products_in_stock=products_in_stock,orders=orders)

@app.route('/admin/add', methods=['GET', 'POST'])
def add():
    form = AddProduct()

    if form.validate_on_submit():
        
        image_url = photos.url(photos.save(form.image.data))# add image url using wtforms
        #saving the product into database

        new_product = Product(name=form.name.data, price=form.price.data, stock = form.stock.data, description = form.description.data, image = image_url)
        #commit to database
        db.session.add(new_product)
        db.session.commit()
        #redirect to admin homepage        
        return redirect(url_for('admin'))


    return render_template('admin/add-product.html', admin=True, form = form)

@app.route('/admin/order/<order_id>')
def order(order_id):
    #query order table to retrieve data on orders
    order = Order.query.filter_by(id=int(order_id)).first()
    return render_template('admin/view-order.html',order=order, admin=True)

if __name__ == '__main__':
    manager.run()