import os
import streamlit as st
from together import Together
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Together AI client
client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "system", "content": """You are a helpful credit card recommendation assistant. 
        Always provide at least one credit card recommendation regardless of the question.
        Focus on explaining the benefits and features of the recommended card."""}
    ]

# Set up the Streamlit page
st.set_page_config(page_title="Credit Card Recommendation Assistant", page_icon="💳")
st.title("Credit Card Recommendation Assistant 💳")
st.subheader("Ask me anything about credit cards!")

def generate_response(messages):
    response = client.chat.completions.create(
        model="meta-llama/Llama-3.3-70B-Instruct-Turbo",
        messages=messages,
        temperature=0.7,
        top_p=0.7,
        top_k=50,
        repetition_penalty=1,
        stop=["<|eot_id|>", "<|eom_id|>"]
    )
    return response.choices[0].message.content.strip()

# Display chat history
for message in st.session_state.messages[1:]:  # Skip the system message
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
if prompt := st.chat_input("Ask about credit cards..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)

    # Generate and display assistant response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = generate_response(st.session_state.messages)
            st.write(response)
            
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": response}) 
