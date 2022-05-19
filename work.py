import mysql.connector
import xlrd

mydb = mysql.connector.connect(
  host="cloudstorage.cwyqmpoiw0xl.us-east-1.rds.amazonaws.com",
  user="symmetric",
  password="encryption",
  database="world"
)
mycursor = mydb.cursor()

wb = xlrd.open_workbook('values.xls')
sheet = wb.sheet_by_index(0)
rows = sheet.nrows
code = sheet.cell_value(1, 0)
code_enc = sheet.cell_value(1, 1)
code_idx = sheet.cell_value(1, 2)
code_iv = sheet.cell_value(1, 3)
code_tag = sheet.cell_value(1, 4)

for currow in range (1, rows):
  code = sheet.cell_value(currow, 0)
  code_enc = sheet.cell_value(currow, 1)
  code_idx = sheet.cell_value(currow, 2)
  code_iv = sheet.cell_value(currow, 3)
  code_tag = sheet.cell_value(currow, 4)
  sql = "UPDATE country SET code_enc = %s, code_idx = %s, code_iv = %s, code_tag = %s WHERE Code = %s"
  val = (code_enc, code_idx, code_iv, code_tag, code)
  mycursor.execute(sql, val)
  mydb.commit()

print(mycursor.rowcount, "record(s) affected")