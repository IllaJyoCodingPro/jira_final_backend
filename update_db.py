from sqlalchemy import create_engine, text
db_url = "mysql+pymysql://root:Yaswanth_2826@localhost/user_story_db"
engine = create_engine(db_url)
with engine.connect() as connection:
    connection.execute(text("ALTER TABLE user_story MODIFY COLUMN project_name VARCHAR(255) NULL;"))
    connection.commit()
print("Column project_name made nullable successfully.")
