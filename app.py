from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Ingredient, Dish, DishIngredient, PriceHistory
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-it'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Функція перерахунку собівартості всіх страв
def recalc_all_dishes():
    dishes = Dish.query.all()
    for dish in dishes:
        total = 0.0
        for di in dish.ingredients:
            total += di.quantity * di.ingredient.current_price
        dish.cost_price = total
        dish.selling_price = total * dish.markup
    db.session.commit()

# Сторінка входу
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Невірний логін або пароль')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Головна панель
@app.route('/')
@login_required
def dashboard():
    ingredients_count = Ingredient.query.count()
    dishes_count = Dish.query.count()
    return render_template('dashboard.html', 
                         ingredients_count=ingredients_count,
                         dishes_count=dishes_count)

# Інгредієнти
@app.route('/ingredients')
@login_required
def ingredients():
    all_ingredients = Ingredient.query.all()
    return render_template('ingredients.html', ingredients=all_ingredients)

@app.route('/ingredient/add', methods=['POST'])
@login_required
def add_ingredient():
    name = request.form['name']
    unit = request.form['unit']
    price = float(request.form['price'])
    new_ing = Ingredient(name=name, unit=unit, current_price=price)
    db.session.add(new_ing)
    db.session.commit()
    flash('Інгредієнт додано')
    return redirect(url_for('ingredients'))

@app.route('/ingredient/edit/<int:id>', methods=['POST'])
@login_required
def edit_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    old_price = ing.current_price
    new_price = float(request.form['price'])
    if old_price != new_price:
        history = PriceHistory(ingredient_id=id, old_price=old_price, new_price=new_price)
        db.session.add(history)
        ing.current_price = new_price
        db.session.commit()
        recalc_all_dishes()
        flash('Ціну оновлено, собівартість страв перераховано')
    else:
        flash('Ціна не змінена')
    return redirect(url_for('ingredients'))

@app.route('/ingredient/delete/<int:id>')
@login_required
def delete_ingredient(id):
    ing = Ingredient.query.get_or_404(id)
    # перевірка, чи використовується в стравах
    used = DishIngredient.query.filter_by(ingredient_id=id).first()
    if used:
        flash('Не можна видалити інгредієнт, що використовується у стравах')
    else:
        db.session.delete(ing)
        db.session.commit()
        flash('Інгредієнт видалено')
    return redirect(url_for('ingredients'))

# Страви
@app.route('/dishes')
@login_required
def dishes():
    all_dishes = Dish.query.all()
    return render_template('dishes.html', dishes=all_dishes)

@app.route('/dish/add', methods=['POST'])
@login_required
def add_dish():
    name = request.form['name']
    markup = float(request.form['markup'])
    new_dish = Dish(name=name, markup=markup)
    db.session.add(new_dish)
    db.session.commit()
    flash('Страву додано')
    return redirect(url_for('dishes'))

@app.route('/dish/<int:id>')
@login_required
def dish_detail(id):
    dish = Dish.query.get_or_404(id)
    ingredients = Ingredient.query.all()
    return render_template('dish_detail.html', dish=dish, ingredients=ingredients)

@app.route('/dish/add_ingredient/<int:dish_id>', methods=['POST'])
@login_required
def add_dish_ingredient(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    ingredient_id = int(request.form['ingredient_id'])
    quantity = float(request.form['quantity'])
    # перевірка на дублікат
    existing = DishIngredient.query.filter_by(dish_id=dish_id, ingredient_id=ingredient_id).first()
    if existing:
        existing.quantity = quantity
    else:
        new_di = DishIngredient(dish_id=dish_id, ingredient_id=ingredient_id, quantity=quantity)
        db.session.add(new_di)
    db.session.commit()
    recalc_all_dishes()
    flash('Склад оновлено, собівартість перераховано')
    return redirect(url_for('dish_detail', id=dish_id))

@app.route('/dish/remove_ingredient/<int:dish_id>/<int:ingredient_id>')
@login_required
def remove_dish_ingredient(dish_id, ingredient_id):
    di = DishIngredient.query.filter_by(dish_id=dish_id, ingredient_id=ingredient_id).first()
    if di:
        db.session.delete(di)
        db.session.commit()
        recalc_all_dishes()
    return redirect(url_for('dish_detail', id=dish_id))

# Калькуляційна карта
@app.route('/calculation/<int:dish_id>')
@login_required
def calculation(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    return render_template('calculation.html', dish=dish)

# Історія змін
@app.route('/price_history')
@login_required
def price_history():
    history = PriceHistory.query.order_by(PriceHistory.change_date.desc()).all()
    return render_template('price_history.html', history=history)

# Створення таблиць і тестового користувача
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin'), role='admin')
        db.session.add(admin)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)