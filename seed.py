import os
import uuid

import psycopg2
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv('DATABASE_URL')

# Connect to RDS (PostgresSQL)
conn = psycopg2.connect(db_url)
conn.autocommit = True
cursor = conn.cursor()


# cursor.execute('CREATE TABLE "User" ('
#                '"id" UUID PRIMARY KEY,'
#                '"name" TEXT NOT NULL,'
#                '"email" TEXT UNIQUE NOT NULL,'
#                '"password" TEXT NOT NULL'
#                ');')
# cursor.execute('CREATE TABLE "File" ('
#                '"id" UUID PRIMARY KEY,'
#                '"url" TEXT NOT NULL,'
#                '"userId" UUID NOT NULL REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE'
#                ');')
# cursor.execute('CREATE TABLE "SharedRecipient" ('
#                '"id" UUID PRIMARY KEY,'
#                '"email" TEXT NOT NULL,'
#                '"token" TEXT UNIQUE NOT NULL,'
#                '"fileId" UUID NOT NULL REFERENCES "File"("id") ON DELETE CASCADE ON UPDATE CASCADE'
#                ');')
# cursor.execute('CREATE TABLE "FileAccess" ('
#                '"id" UUID PRIMARY KEY,'
#                '"email" TEXT NOT NULL,'
#                '"fileId" UUID NOT NULL REFERENCES "File"("id") ON DELETE CASCADE ON UPDATE CASCADE,'
#                'UNIQUE ("email", "fileId")'
#                ');')

# insert a new record
cursor.execute('INSERT INTO public."User" (id, name, email, password) VALUES (%s, %s, %s, %s);',
               (str(uuid.uuid4()), 'John Doe', 'user@web.com', 'password'))
conn.commit()

# get all the records in the user table
cursor.execute('SELECT * FROM public."User";')
users = cursor.fetchall()

# print the records
for user in users:
    print(user)
