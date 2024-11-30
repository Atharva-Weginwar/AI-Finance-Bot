import streamlit as st
import os
import together
from googleapiclient.discovery import build
import time
from datetime import datetime, timedelta
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

# Initialize API clients
together.api_key = os.getenv("TOGETHER_API_KEY")
google_client = build("customsearch", "v1", developerKey=os.getenv("GOOGLE_API_KEY"))

# Rate limiting setup
class RateLimiter:
    def __init__(self):
        self.together_calls = defaultdict(list)
        self.google_calls = defaultdict(list)
    
    def can_call_together(self, user_id):
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        # Clean old calls
        self.together_calls[user_id] = [
            call_time for call_time in self.together_calls[user_id] 
            if call_time > hour_ago
        ]
        return len(self.together_calls[user_id]) < 60

    def can_call_google(self, user_id):
        now = datetime.now()
        day_ago = now - timedelta(days=1)
        # Clean old calls
        self.google_calls[user_id] = [
            call_time for call_time in self.google_calls[user_id] 
            if call_time > day_ago
        ]
        return len(self.google_calls[user_id]) < 100

    def log_together_call(self, user_id):
        self.together_calls[user_id].append(datetime.now())

    def log_google_call(self, user_id):
        self.google_calls[user_id].append(datetime.now())

rate_limiter = RateLimiter()

# Search function
def search_financial_info(query, priority_sites=True):
    if not rate_limiter.can_call_google("default"):
        return "Rate limit exceeded for search. Please try again later."
    
    sites_filter = "site:thepointsguy.com OR site:nerdwallet.com" if priority_sites else ""
    search_query = f"{query} {sites_filter}"
    
    try:
        rate_limiter.log_google_call("default")
        results = google_client.cse().list(
            q=search_query,
            cx=os.getenv("GOOGLE_CSE_ID"),
            num=5
        ).execute()
        
        return results.get("items", [])
    except Exception as e:
        return f"Error performing search: {str(e)}"

# AI response generation
def generate_ai_response(query, search_results, additional_context=""):
    if not rate_limiter.can_call_together("default"):
        return "Rate limit exceeded for AI responses. Please try again later."
    
    context = "\n".join([
        f"Title: {result['title']}\nSnippet: {result['snippet']}\nLink: {result['link']}"
        for result in search_results[:3]
    ])
    
    system_message = """You are a helpful AI assistant specializing in personal finance advice. 
    When discussing financial products:
    1. Always provide concise, structured responses
    2. For credit cards: Compare options in a clear pros/cons format
    3. For investments: Include risk levels and time horizon considerations
    4. For loans: Compare rates and terms
    5. Always conclude with a clear "Recommended Action" section
    6. Keep responses focused and actionable"""
    
    prompt = f"""Based on the following information, answer this question: "{query}"

Context:
{context}

Additional User Context:
{additional_context}

Please structure your response as follows:
1. Brief Overview (2-3 sentences)
2. Key Comparisons (if applicable, in pros/cons format)
3. Recommended Action
4. Additional Considerations

Keep the response concise and actionable."""
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]
    
    try:
        rate_limiter.log_together_call("default")
        client = together.Together()
        response = client.chat.completions.create(
            model="meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            messages=messages,
            max_tokens=512,
            temperature=0.7,
            top_p=0.7,
            top_k=50,
            repetition_penalty=1,
            stop=["<|eot_id|>","<|eom_id|>"],
            stream=True
        )
        
        response_text = ""
        try:
            for chunk in response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    if chunk.choices[0].delta.content is not None:
                        response_text += chunk.choices[0].delta.content
        except Exception as e:
            print(f"Error in streaming: {str(e)}")
        
        if not response_text.strip():
            return "I apologize, but I couldn't generate a response. Please try again."
            
        return response_text.strip()
    except Exception as e:
        return f"Error generating response: {str(e)}"

# Streamlit UI
def main():
    st.title("AI Finance Assistant")
    
    # Sidebar for topic filtering
    st.sidebar.header("Topics")
    selected_topic = st.sidebar.selectbox(
        "Filter by Topic",
        ["All Topics", "Credit Cards", "Investments", "Loans", "Insurance", 
         "Travel Rewards", "Banking"]
    )
    
    # Additional inputs for Credit Cards
    credit_score = None
    current_cards = None
    if selected_topic == "Credit Cards":
        col1, col2 = st.columns(2)
        with col1:
            credit_score = st.number_input("Your Credit Score", min_value=300, max_value=850, value=700)
        with col2:
            current_cards = st.text_area("Current Credit Cards (one per line)", height=100)
    
    # Main chat interface
    st.write("Ask me anything about personal finance!")
    
    query = st.text_input("Your question:")
    
    if query:
        # Add additional context to query based on topic and inputs
        additional_context = ""
        if selected_topic == "Credit Cards" and credit_score and current_cards:
            additional_context = f"\nUser's credit score: {credit_score}\nCurrent credit cards: {current_cards}"
        
        # Add topic to query if specific topic selected
        search_query = f"{query} {selected_topic}" if selected_topic != "All Topics" else query
        
        # Search for information
        search_results = search_financial_info(search_query)
        
        if isinstance(search_results, str):  # Error message
            st.error(search_results)
        else:
            # Generate response
            response = generate_ai_response(query, search_results, additional_context)
            
            # Display response if we have one
            if response and not response.startswith("Error"):
                st.write("### Response")
                st.write(response)
            elif response:
                st.error(response)
                
            # Display sources
            if search_results:
                st.write("### Sources")
                for result in search_results:
                    st.write(f"- [{result['title']}]({result['link']})")

if __name__ == "__main__":
    main() 
    