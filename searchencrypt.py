import pandas as pd
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import hashes, hmac
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
import os
import sys
import json
from getpass import getpass
from base64 import b64encode, b64decode
import mysql.connector
from xlwt import Workbook


def connectToDB(hostname, uname, pwd, dbase):
    db = mysql.connector.connect(
        host=hostname,
        user='symmetric',
        password='encryption',
        database=dbase
    )
    return db


# Key derivation using Scrypt
# This should be run twice, once to make an index key and once to make an encryption key, both using different salts
def deriveKey(pwd, salt):
    kdf = Scrypt(
        salt=salt,
        length=32,
        n=2 ** 14,
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
        n=2 ** 14,
        r=8,
        p=1,
    )
    bidx = kdf.derive(plaintext)
    return bidx


# This is a placeholder. We'll decide what database and what column to encrypt later
def search_by_blindindex(db, plaintext, indexKey, enckey, uname):
    index = b64encode(getBlindIndex(indexKey, plaintext.encode('UTF-8'))).decode('UTF-8')
    cursor = db.cursor(dictionary=True)
    query = "SELECT code_iv, code_enc, code_tag FROM country WHERE code_idx=\"{cidx}\"".format(cidx = index)
    cursor.execute(query)
    result = cursor.fetchall()
    #print(result)

    df = pd.read_sql_query(query, con = db)
    code_iv = df.loc[0:, 'code_iv'].to_string().split(' ')[4]
    code_enc = df.loc[0:, 'code_enc'].to_string().split(' ')[4]
    code_tag = df.loc[0:, 'code_tag'].to_string().split(' ')[4]
    try:
        plaintext = decrypt(enckey, uname.encode('UTF-8'), b64decode(code_iv.encode('UTF-8')), b64decode(code_enc.encode('UTF-8')), b64decode(code_tag.encode('UTF-8')))
    except:
        return "An error has occurred"


    print(plaintext)
    return "Encrypted: " + code_enc + ", Decrypted: " + plaintext.decode('UTF-8')

# Test
def testdecrypt(db):
    cursortest = db.cursor(dictionary=True, buffered=True)
    querytest = "SELECT code_iv, code_enc, code_tag FROM country WHERE Code = 'ABW';"
    cursortest.execute(querytest)
    resulttest = cursortest.fetchall()
    dftest = pd.read_sql_query(querytest, con=db)
    code_ivtest = dftest.loc[0:, 'code_iv'].to_string().split(' ')[4]
    code_enctest = dftest.loc[0:, 'code_enc'].to_string().split(' ')[4]
    code_tagtest = dftest.loc[0:, 'code_tag'].to_string().split(' ')[4]
    keytest = deriveKey(b"hello", os.urandom(12))
    unametest = "hello"
    try:
        plaintext = decrypt(keytest, unametest.encode('UTF-8'), b64decode(code_ivtest.encode('UTF-8')), b64decode(code_enctest.encode('UTF-8')), b64decode(code_tagtest.encode('UTF-8')))
        print(plaintext)
    except:
        print("An error has occurred")

# This is just in the case that the file exists but is empty

uname = "symmetric"
pwd = "encryption"



# We're running the key derviation twice - once to generate an encryption key and once to generate a blind index key


db = connectToDB('cloudstorage.cwyqmpoiw0xl.us-east-1.rds.amazonaws.com', 'symmetric', 'encryption', 'world')