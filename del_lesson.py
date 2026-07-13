import psycopg2
conn = psycopg2.connect('dbname=surod_rag user=postgres password=1234')
cur = conn.cursor()
cur.execute("DELETE FROM lessons WHERE id=23")
conn.commit()
print("Deleted lesson 23")
