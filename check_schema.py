from sqlalchemy import create_engine, inspect
db_url = "mysql+pymysql://root:Yaswanth_2826@localhost/user_story_db"
engine = create_engine(db_url)
inspector = inspect(engine)
columns = inspector.get_columns('user_story')
for column in columns:
    print(f"{column['name']} | {column['nullable']}")
