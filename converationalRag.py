from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_huggingface import HuggingFaceEmbeddings
import os
import streamlit as st
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.document_loaders.pdf import PyPDFLoader
from langchain.chains import history_aware_retriever, conversational_retrieval
from langchain.chains.combine_documents import create_stuff_documents_chain
from dotenv import load_dotenv

load_dotenv()

st.title("Conversational RAG with PDF Upload")
st.write("Upload a PDF and ask questions about its content.")

api_key = st.text_input("Enter your Groq API key:", type="password")

if api_key:
    llm = ChatGroq(api_key=api_key, model="llama-3.1-70b-versatile") #use any model you want
    session_id = st.text_input("Enter a session ID:", value="default_session")
    
    if "store" not in st.session_state:
        st.session_state.store = {}
    
    uploaded_files = st.file_uploader("Upload documents (PDF format)", type=['pdf'], accept_multiple_files=True)
    
    if uploaded_files:
        documents = []
        for uploaded_file in uploaded_files:
            temp_path = "./temp.pdf"
            with open(temp_path, 'wb') as f:
                f.write(uploaded_file.getvalue())
            loader = PyPDFLoader(temp_path)
            docs = loader.load()
            documents.extend(docs)
        
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        splits = text_splitter.split_documents(documents)
        
        embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        vector_store = Chroma.from_documents(documents=splits, embedding=embedding_model)
        
        retriever = vector_store.as_retriever()
        
        # Fixed prompt template
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
            ("placeholder", "{chat_history}"),
            ("human", "{input}")
        ])
        
        # Fixed function call
        history_aware_retriev = history_aware_retriever(
            llm, retriever, contextualize_q_prompt
        )
        
        # Fixed prompt template
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise.\n\n{context}"),
            ("placeholder", "{chat_history}"),
            ("human", "{input}")
        ])
        
        # Fixed chain creation
        question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
        rag_chain = conversational_retrieval(history_aware_retriev, question_answer_chain)
        
        def get_session_history(session: str) -> BaseChatMessageHistory:
            if session not in st.session_state.store: 
                st.session_state.store[session] = ChatMessageHistory()
            return st.session_state.store[session]
        
        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain,
            get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history"
        )
        
        user_input = st.text_input("Enter a question to search:")
        if user_input:
            session_history = get_session_history(session_id)
            response = conversational_rag_chain.invoke(
                {"input": user_input},
                config={
                    "configurable": {"session_id": session_id}
                }
            )
            st.write("**Answer:**", response['answer'])
            
            
            if st.checkbox("Show chat history"):
                st.write("**Chat History:**")
                for message in session_history.messages:
                    st.write(f"- {message.type}: {message.content}")
else:
    st.warning("Please enter your Groq API key to continue.")