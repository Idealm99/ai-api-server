# sqlite 사용해서 히스토리를 저장합니다 
# 파일은 자동 생성이 됩니다
# 원문에 있는 것들을 그대로 작성하였고 GPT 도움을 받았습니다 ㅎㅎ
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
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
        # ✅ LangGraph와 LangChain에서 사용할 모델 초기화
        self.model = init_chat_model(model_name, model_provider=model_provider)
        self.llm = ChatOpenAI(model_name=model_name)

        # ✅ LangChain용 Prompt 설정
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant. Answer all questions to the best of your ability in {language}."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ]
        )

        # ✅ LangGraph는 MemorySaver 사용 (SQLiteSaver 제거)
        self.memory = MemorySaver()

        # ✅ SQLite 기반 대화 기록 저장
        self.chat_message_history = SQLChatMessageHistory(
            session_id="test_session_id", connection_string="sqlite:///sqlite.db"
        )

        # ✅ LangGraph 워크플로우 설정
        self.workflow = self._build_workflow()
        self.app = self.workflow.compile(checkpointer=self.memory)

        # ✅ LangChain의 `RunnableWithMessageHistory`로 RAG 적용 가능하도록 설정
        self.chain = self.prompt_template | self.llm
        self.chain_with_history = RunnableWithMessageHistory(
            self.chain,
            lambda session_id: SQLChatMessageHistory(session_id=session_id, connection_string="sqlite:///sqlite.db"),
            input_messages_key="question",
            history_messages_key="history",
        )

    def _build_workflow(self):
        workflow = StateGraph(state_schema=self.State)
        workflow.add_node("model", self._call_model)
        workflow.add_edge(START, "model")
        return workflow

    def _call_model(self, state: State):
        """
        ✅ SQLite에서 과거 대화 기록을 불러와 LangGraph에서 사용
        """
        # ✅ SQLite에서 대화 기록 가져오기
        past_messages = self.chat_message_history.messages  # 대화 기록 리스트

        # ✅ LangGraph 내부 상태 메시지와 SQLite 기록을 합치기
        all_messages = past_messages + state["messages"]

        # ✅ 최근 사용자의 질문 추출
        last_human_message = next((msg.content for msg in reversed(all_messages) if isinstance(msg, HumanMessage)), None)
        if last_human_message is None:
            last_human_message = "Hello, how can I help you?"  # 기본 질문 설정

        # ✅ 프롬프트 생성 (과거 기록 반영 + question 추가)
        prompt = self.prompt_template.invoke({
            "history": all_messages,
            "language": state["language"],
            "question": last_human_message,  # 🔹 추가된 부분
        })

        # ✅ 모델 실행
        response = self.model.invoke(prompt)

        # ✅ AI 응답을 LangGraph 상태에도 저장
        return {"messages": all_messages + [response]}


    def translate(self, text: str, language: str, session_id: str = "default_thread"):
        """
        ✅ 사용자의 입력을 받아 번역하고, 대화 기록을 SQLite에 저장
        """
        input_messages = [HumanMessage(text)]
        config = {"configurable": {"thread_id": session_id}}

        # ✅ SQLite에 사용자의 입력 저장
        self.chat_message_history.add_user_message(text)

        # ✅ LangGraph를 사용하여 번역 실행
        output = self.app.invoke({"messages": input_messages, "language": language}, config)

        # ✅ AI 응답을 SQLite에도 저장하여 동기화 유지
        ai_response = output["messages"][-1].content
        self.chat_message_history.add_ai_message(ai_response)

        return ai_response
