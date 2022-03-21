from flask.globals import current_app
from app.forms import LoginForm, RegisterForm, ResetRequestForm, PasswordResetForm
from . import auth
from flask import Flask, request, make_response, redirect, render_template, session, url_for, abort, flash
from models import User, Community, Post, Comment, get_user, get_by_email
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from db_service import db
from urllib.parse import urlparse, urljoin
from mail_service import mail
from flask_mail import Message


# Flask Mail initialization


# url safe implementation as seen in the Flask docs
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and \
           ref_url.netloc == test_url.netloc

# function for sending password reset email with Flask-Mail
# @param user: the user requesting the password reset
def send_reset_email(user):
    token = user.generate_token()
    msg = Message('Password Reset', sender='noreply@goodgamewebapp.com', 
                    recipients=[user.email])
    msg.body = f"""Hey! We've hear that you somehow forgot your password, click the 
following link to set a new password. This link will expire in one hour:
{url_for('auth.reset_password', token=token, _external=True)}

If you didn't make this request, ignore this message.

Don't respond to these emails, they're autogenerated for user assistance purposes.
"""
    mail.send(msg) 


###
### authentication routes for handling login, logout and register
###
@auth.route('/login', methods=['GET', 'POST'])
def login():
    login_form = LoginForm()

    if login_form.validate_on_submit():
        user = get_user(login_form.username.data)
        
        if user:
            if check_password_hash(user.password, login_form.password.data):
                login_user(user)
                
                next = request.args.get('next')
                if not is_safe_url(next):
                    return abort(404)

                return redirect(next or url_for('start'))
            
            else:
                flash('Invalid password, please re enter credentials')
                return redirect(url_for('auth.login'))

        flash('No user registered with that username')
        return redirect(url_for('auth.login'))

    return render_template('login.html', login_form=login_form)



@auth.route('/signup', methods=['GET', 'POST'])
def signup(): 
    signup_form = RegisterForm()
    context = {
        'signup_form': signup_form
    }
    
    if signup_form.validate_on_submit():
        
        username = signup_form.username.data
        email = signup_form.email.data
        password = signup_form.password.data
        
        registered = get_user(username)
        email_used = get_by_email(email)
        if registered or email_used:
            flash('These credentials are already in use, check your email or username')
            return redirect(url_for('auth.signup'))

        new_user = User(username=username, email=email, 
                        password=generate_password_hash(password, method='pbkdf2:sha512'))
        
        db.session.add(new_user)
        db.session.commit()

        user = get_user(signup_form.username.data)
        login_user(user)

        next = request.args.get('next')
        if not is_safe_url(next):
            return abort(404)

        return redirect(next or url_for('start'))

    return render_template('signup.html', **context)

 
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('start'))


@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    form = ResetRequestForm()
    if form.validate_on_submit():
        user = get_by_email(form.email.data) 
        if user:
            send_reset_email(user)
        flash('Check your Email inbox in order to reset your password', 'info')
        return redirect(url_for('auth.forgot_password'))
    flash('Enter the email you registered to receive a recovery link.', 'info')
    return render_template('forgot_password.html', form=form)

@auth.route('/reset_password_request/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('start')) 
    
    user = User.validate_token(token)
    if user is None:
        flash('The url you are trying to reach has an expired or invalid token', 'info')
        return redirect(url_for('auth.login'))

    form = PasswordResetForm()
    if form.validate_on_submit():
        user.password = generate_password_hash(form.password.data, method='pbkdf2:sha512')
        db.session.commit()
        flash('Your password has been updated, you can log in now.', 'info')
        return redirect(url_for('auth.login'))
    flash('Enter your new password, it must be between 8 and 20 characters long', 'info')
    return render_template('reset_password.html', form=form)
