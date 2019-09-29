import os
import base64

from flask import Flask, render_template, request, redirect, url_for, session
from model import Donation, Donor, User
from passlib.hash import pbkdf2_sha256
from playhouse.db_url import connect
from peewee import *
import peewee
import psycopg2 # for heroku

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY').encode()

@app.route('/')
def home():
    return redirect(url_for('all'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.select().where(User.name == request.form['name']).get()

        if user and pbkdf2_sha256.verify(request.form['password'], user.password):
            session['username'] = request.form['name']
            return redirect(url_for('all'))

        return render_template('login.jinja2', error="Incorrect username or password.")

    else:
        return render_template('login.jinja2') 

@app.route('/donations/')
def all():
    donations = Donation.select()
    return render_template('donations.jinja2', donations=donations)

@app.route('/donors/')
def all_donors():
    donors = Donor.select()
    return render_template('donors.jinja2', donors=donors)


@app.route('/new/', methods=['GET', 'POST'])
def new_donor():
    # print(session)
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        name=request.form['name']
        if name:
            try:
                donor = Donor(name=name)
                donor.save()
            except peewee.IntegrityError:
                return render_template('new.jinja2', error=f"Donor {name} already in Database")
            except psycopg2.errors.UniqueViolation:
                return render_template('new.jinja2', error=f"Donor {name} already in Database")
            else:
                return redirect(url_for('all_donors'))
        else:
            return render_template('new.jinja2', error="Please enter donor name")
    else:
        return render_template('new.jinja2')

@app.route('/delete/', methods=['GET', 'POST'])
def delete_donor():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
    
        name=request.form['name']
        print(f"+++ {name} to delete")
        if name is None:
            return render_template('delete.jinja2')
        else:
            try:
                donor = Donor.select().where(Donor.name == name).get()
                # query = Note.delete().where(Note.id > 3)
                # n = query.execute()

                query1 = Donation.delete().where(Donation.donor_id == donor.id)
                query2 = Donor.delete().where(Donor.name == donor.name)
                m = query1.execute()
                n = query2.execute()
            except Donor.DoesNotExist:          # no donor in db
                return render_template('delete.jinja2', error="Donor not found.", not_found=name) 
            except psycopg2.errors.InFailedSqlTransaction:
                return render_template('delete.jinja2', error="Heroku - psycopg2.errors.InFailedSqlTransaction") 
            return redirect(url_for('all_donors'))
    else:
        return render_template('delete.jinja2')


@app.route('/add', methods=['GET', 'POST'])
def select_donor():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    name = request.args.get('donor', None)
    if name is None:
        return render_template('add.jinja2')
    else:
        try:
            donor = Donor.select().where(Donor.name == name).get()
            session['donor'] = donor.name
        except Donor.DoesNotExist:          # no donor in db
            return render_template('add.jinja2', error="Donor not found.", not_found=name) 
            
        # return render_template('add_donation.jinja2', donor=donor.name)
        return redirect(url_for('add_donation'))

@app.route('/add/donation/', methods=['GET', 'POST'])
def add_donation():

    if 'username' not in session:
        return redirect(url_for('login'))

    donor = Donor.select().where(Donor.name == session['donor']).get()
    # donation = request.args.get('value', None)
    
    if request.method == 'POST':
        try:
            value = int(request.form['number'])
        except ValueError:
            return render_template('add_donation.jinja2', donor=donor.name, error="Donation should be integer")

        donation = Donation(donor=donor, value=value)
        donation.save()
        return redirect(url_for('all'))
    else:
        return render_template('add_donation.jinja2', donor=donor.name)
        
@app.route('/stats/')
def statistic():
    # database = connect(os.environ.get('DATABASE_URL', 'sqlite:///my_database.db'))
    # database = SqliteDatabase('my_database.db')
    
    try:
        # database.connect()
        # database.execute_sql('PRAGMA foreign_keys = ON;')
        
        query = (Donor
                        .select(Donor.name.alias('name'),
                                fn.COUNT(Donation.donor_id).alias('num'),
                                fn.SUM(Donation.value).alias('total'),
                                fn.AVG(Donation.value).alias('avg'))
                        .join(Donation,
                            JOIN.LEFT_OUTER,
                            on=(Donor.id == Donation.donor_id))
                        # .object()
                        .group_by(Donor.name)
                        .order_by(fn.SUM(Donation.value).desc())
                )
        
        report_ = []
        for result in query:       ## cursor
            donor_ = {}
            donor_['name'] = result.name,
            donor_['number'] = result.num if result.num else 0
            donor_['total'] = result.total if result.total else 0.00
            donor_['avg'] = result.avg if result.avg else 0.00
            report_.append(donor_)
    except Exception as e:
            print(e)
    finally:
        # database.close()
        pass

    return render_template('stats.jinja2', report=report_)               


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 6738))
    app.run(host='0.0.0.0', port=port )
