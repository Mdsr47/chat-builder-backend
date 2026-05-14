import os
from dotenv import load_dotenv
load_dotenv()
from database import supabase_client

if supabase_client:
    try:
        # Create a dummy file
        with open("dummy.txt", "wb") as f:
            f.write(b"Hello Supabase")
            
        print("Uploading...")
        # Upload using file path
        with open("dummy.txt", "rb") as f:
            res = supabase_client.storage.from_("chatbot_indexes").upload(
                file=f,
                path="test/dummy2.txt",
                file_options={"upsert": "true"}
            )
        print("Upload result:", res)
    except Exception as e:
        print("Error:", repr(e))
else:
    print("No supabase client initialized.")
