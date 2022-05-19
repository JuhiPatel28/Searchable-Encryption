from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import os
import sys
import json
from getpass import getpass
from base64 import b64encode, b64decode
import mysql.connector

def connectToDB(hostname, uname, pwd, dbase):
	db = mysql.connector.connect(
		host=hostname,
		user=uname,
		password=pwd,
		database=dbase
	)
	return db

# Key derivation using Scrypt
# This should be run twice, once to make an index key and once to make an encryption key, both using different salts
def deriveKey(pwd, salt):
	kdf = Scrypt(
		salt=salt,
		length=32,
		n=2**14,
		r=8,
		p=1,
	)
	key = kdf.derive(pwd)
	return key

def encrypt(key, plaintext, associated_data):
	# Generate a random 96-bit IV.
	iv = os.urandom(12)

	# Construct an AES-GCM Cipher object with the given key and a
	# randomly generated IV.
	encryptor = Cipher(
		algorithms.AES(key),
		modes.GCM(iv),
	).encryptor()

	# associated_data will be authenticated but not encrypted,
	# it must also be passed in on decryption.
	encryptor.authenticate_additional_data(associated_data)

	# Encrypt the plaintext and get the associated ciphertext.
	# GCM does not require padding.
	ciphertext = encryptor.update(plaintext) + encryptor.finalize()

	return iv, ciphertext, encryptor.tag
    
def decrypt(key, associated_data, iv, ciphertext, tag):
	# Construct a Cipher object, with the key, iv, and additionally the
	# GCM tag used for authenticating the message.
	decryptor = Cipher(
		algorithms.AES(key),
		modes.GCM(iv, tag),
	).decryptor()

	# We put associated_data back in or the tag will fail to verify
	# when we finalize the decryptor.
	decryptor.authenticate_additional_data(associated_data)

	# Decryption gets us the authenticated plaintext.
	# If the tag does not match an InvalidTag exception will be raised.
	return decryptor.update(ciphertext) + decryptor.finalize()

# The blind index is also using Scrypt with the index key as the salt, as per the article's recommendation
def getBlindIndex(indexKey, plaintext):
	kdf = Scrypt(
		salt=indexKey,
		length=32,
		n=2**14,
		r=8,
		p=1,
	)
	bidx = kdf.derive(plaintext)
	return bidx

# This is a placeholder. We'll decide what database and what column to encrypt later
def findHumansBySSN(db, plaintext, indexKey):
	index = getBlindIndex(indexKey, plaintext)
	cursor = db.cursor()
	cursor.execute("SELECT * FROM humans WHERE ssn_bidx = " + index)
	result = cursor.fetchall()
	return result
	
# Our users file is loaded as a dictionary where the keys are the usernames and the values are tuples containing (in order) the encryption salt and index salt
userfile = open('users.json', 'r+')
# This is just in the case that the file exists but is empty
try:
	users = json.load(userfile)
except:
	users = {}
uname = input("Username: ")
pwd = getpass()
if not uname in users.keys():
	response = input("This user does not exist. Would you like to create a new user with this name? (Y/N): ")
	# In the case of a new user, we have to generate both salts
	if response.lower() == 'y':
		encsalt = os.urandom(16)
		idxsalt = os.urandom(16)
		users[uname] = (b64encode(encsalt).decode('UTF-8'), b64encode(idxsalt).decode('UTF-8'))
		json.dump(users, userfile, indent = 6)
	else:
		print("Exiting...")
		sys.exit()
userfile.close()

encsalt = users[uname][0]
idxsalt = users[uname][1]
# We're running the key derviation twice - once to generate an encryption key and once to generate a blind index key
enckey = deriveKey(pwd.encode('UTF-8'), b64decode(encsalt.encode('UTF-8')))
idxkey = deriveKey(pwd.encode('UTF-8'), b64decode(idxsalt.encode('UTF-8')))

db = connectToDB('cloudstorage.cwyqmpoiw0xl.us-east-1.rds.amazonaws.com', 'symmetric', 'encryption', 'world')
cursor = db.cursor(dictionary=True)
cursor.execute("SELECT code FROM country")
for row in cursor:
    print ("plaintext", row["code"])
    plaintext = row["code"].encode('UTF-8')
    # We're gonna need to append the IV to the end of the record, or give it it's own column. Same with the tag.
    iv, ciphertext, tag = encrypt(enckey, plaintext, uname.encode('UTF-8'))
    print("ciphertext", ciphertext)
    blindindex = getBlindIndex(idxkey, plaintext)
    print("blindindex", blindindex)
	
