from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from typing import Sequence
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict
from langchain_community.chat_message_histories import SQLChatMessageHistory

from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI
# 환경 변수 로딩
load_dotenv()

class TranslationModel:
    class State(TypedDict):
        messages: Annotated[Sequence[BaseMessage], add_messages]
        language: str
    
    def __init__(self, model_name="gpt-4o-mini", model_provider="openai"):
        self.model = init_chat_model(model_name, model_provider=model_provider)
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant. Answer all questions to the best of your ability in {language}."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )
        self.memory = MemorySaver()
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.memory)
        self.chat_message_history = SQLChatMessageHistory(session_id="test_session_id", connection_string="sqlite:///sqlite.db")
        self.chain = self.prompt_template | ChatOpenAI()
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            lambda session_id: SQLChatMessageHistory(session_id=session_id, connection_string="sqlite:///sqlite.db"),
            input_messages_key="question",
            history_messages_key="history",)

        # chat_message_history.add_user_message("Hello")
        # chat_message_history.add_ai_message("Hi")
    
    def _build_workflow(self):
        workflow = StateGraph(state_schema=self.State)
        workflow.add_node("model", self._call_model)
        workflow.add_edge(START, "model")
        return workflow
    
    def _call_model(self, state: State):
        prompt = self.prompt_template.invoke(state)
        response = self.model.invoke(prompt)
        return {"messages": response}
    
    def translate(self, text: str, language: str, session_id: str = "default_thread"):
        input_messages = [HumanMessage(text)]
        config = {"configurable": {"thread_id": session_id}}

        self.chain_with_history.invoke({"question": "Hi! I'm bob"}, config=config)
        
        output = self.app.invoke({"messages": input_messages, "language": language}, config)
        return output["messages"][-1].content