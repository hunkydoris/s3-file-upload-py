import mimetypes
import os
import secrets
import time
import uuid

import boto3
import psycopg2
import requests
from flask import Flask, request, render_template, redirect

from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__, template_folder='templates')
s3_bucket = os.getenv('AWS_S3_BUCKET')
ses_url = os.getenv('AWS_SES_URL')
database_url = os.getenv('DATABASE_URL')

# Connect to RDS (PostgresSQL)
conn = psycopg2.connect(database_url)
cursor = conn.cursor()

# S3 client
s3_client = boto3.client('s3',
                         aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                         aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                         region_name=os.getenv('AWS_S3_REGION')
                         )

user_sessions = {}


@app.route('/')
def index():
    if not is_authenticated():
        return redirect('/login')
    return render_template('upload.html')


@app.route('/login', methods=['GET'])
def login_home():
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    # Validate email and password from the database
    cursor.execute('SELECT id, password FROM "User" WHERE email = %s', (email,))
    user = cursor.fetchone()
    if user and user[1] == password:
        session_token = secrets.token_urlsafe(16)
        user_sessions[session_token] = user[0]  # Save the user ID in the session
        response = redirect('/')
        response.set_cookie('session_token', session_token)  # Set the session token as a cookie
        return response
    else:
        return "Invalid email or password", 401


def is_authenticated():
    session_token = request.cookies.get('session_token')
    return session_token in user_sessions


@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    emails = request.form['emails'].split(',')

    if len(emails) == 0:
        return "At least one email is required", 400
    if len(emails) > 5:
        return "Maximum 5 email addresses allowed", 400

    _, file_extension = os.path.splitext(file.filename)

    filename = str(uuid.uuid4()) + file_extension

    # detect content type of file
    mimetype = (mimetypes.guess_type(file.filename)[0] or
                'application/octet-stream')

    s3_client.upload_fileobj(file, s3_bucket, filename, ExtraArgs={
        'ContentType': mimetype,
    })

    access_url = f'https://{s3_bucket}.s3.us-west-2.amazonaws.com/{filename}'

    # Get the user id from cookie
    user_id = user_sessions[request.cookies.get('session_token')]

    # Store file info in DB
    file_id = str(uuid.uuid4())
    cursor.execute('INSERT INTO public."File" ("id", "url", "userId") VALUES (%s, %s, %s);',
                   (file_id, access_url, user_id))

    recipients = []
    # Store shared recipients in DB
    for email in emails:
        recipient_id = str(uuid.uuid4())
        token = str(uuid.uuid4())
        recipients.append((recipient_id, email, token, file_id))

        cursor.execute(
            'INSERT INTO public."SharedRecipient" ("id", "email", "token", "fileId") VALUES (%s, %s, %s, %s);',
            (recipient_id, email, token, file_id))
    conn.commit()

    for recipient in recipients:
        recipient_id, email, token, file_id = recipient
        access_url = f'http://localhost:4000/access-file?token={token}'
        data = {
            'to': email,
            'subject': 'File shared with you',
            'text': f'You have been shared a file. Click on the link to access it: {access_url}',
            'html': f'<p>You have been shared a file. Click on the link to access it: <a href="{access_url}">{access_url}</a></p>',
        }

        requests.post(ses_url, json=data)
        time.sleep(1)

    return "File uploaded and emails sent!", 200


@app.route('/access-file', methods=['GET'])
def access_file():
    token = request.args.get('token')

    if not token:
        return "Token not provided", 400

    # Get file id from token
    cursor.execute('SELECT "fileId", "email"  FROM public."SharedRecipient" WHERE "token" = %s', (token,))
    file_info = cursor.fetchone()

    if not file_info:
        return "Invalid token", 400
    file_id = file_info[0]

    # Check if all the recipients have accessed the file
    cursor.execute('SELECT COUNT(*) FROM public."SharedRecipient" WHERE "fileId" = %s', (file_id,))
    total_recipients = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM public."FileAccess" WHERE "fileId" = %s', (file_id,))
    total_accessed = cursor.fetchone()[0]

    # Get the file URL
    cursor.execute('SELECT "url" FROM public."File" WHERE "id" = %s', (file_id,))
    url = cursor.fetchone()[0]

    if total_recipients == total_accessed:
        # Delete file from S3 bucket
        filename = url.split('/')[-1]
        s3_client.delete_object(Bucket=s3_bucket, Key=filename)

        return "All recipients have accessed this file. The file has been deleted.", 400

    #  get email from the database
    email = file_info[1]
    cursor.execute(
        'INSERT INTO public."FileAccess" ("id", "email", "fileId") VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;',
        (str(uuid.uuid4()), email, file_id))
    conn.commit()

    return redirect(url)


if __name__ == '__main__':
    app.run(host='localhost', port=4000, debug=True)
