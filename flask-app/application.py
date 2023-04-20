import os
from typing import Dict
from aiohttp_retry import Any
from flask import Flask, request
from langchain import PromptTemplate
from twilio.twiml.messaging_response import MessagingResponse
import json

from langchain.llms import OpenAI
from langchain.memory import ConversationSummaryBufferMemory

from supabase import create_client, Client
from twilio_utils import validate_twilio_request

application = Flask(__name__)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

@application.route('/')
def index():
    return json.dumps({"health": "ok"})

@application.route('/twilio', methods=["POST"])
@validate_twilio_request
def twilio_callback():
    try: 
        sender = request.values.get('From', None)
        reciever = request.values.get('To', None)
        incoming_msg = request.values.get('Body', None)

        user_res = supabase.table("users").select("*").eq("phone_number", sender).limit(1).execute().data
        if len(user_res) == 0:
            print("user")
            return "user not found", 200
        sender_name = user_res[0]["name"]
        sender_user_id = user_res[0]["id"]

        group_member_res = supabase.table("group_members").select("*").eq("twilio_phone_number", reciever).eq("user_id", sender_user_id).execute().data
        if len(group_member_res) == 0:
            return "group member not found", 200
        
        group_id = group_member_res[0]["group_id"]
        group_res = supabase.table("groups").select("*").eq("id", group_id).execute().data
        if len(group_res) == 0:
            return "group not found", 200
        group = group_res[0]

        llm_message = get_llm_message(group, incoming_msg, sender_name)

        resp = MessagingResponse()
        res  = f"{llm_message}"
        resp.message(res)

        return str(resp)
        
    except Exception as e:
        print(e)
        return "error", 500

llm = OpenAI()
ai_prompt = PromptTemplate(input_variables=[], template="AI Motvator: ")
human_prompt = PromptTemplate(input_variables=["name", "msg"], template="{name}: {msg}")

def get_llm_message(group: Dict[str, Any], incoming_msg: str, sender_name: str):
    if group["memory"] == None:
        initial_prompt = (
            group["base_prompt"] 
            + "\n" 
            + group["initial_context"] 
            + human_prompt.format(name=sender_name, msg=incoming_msg)
            + ai_prompt.format()
        )
        return llm(initial_prompt).strip()

if __name__ == "__main__":
    application.debug = True
    application.run()