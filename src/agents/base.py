"""
Base agent class using LangChain
"""
from typing import Optional, Any
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel

from src.core.config import settings


class BaseAgent:
    """Base class for all LangChain-based agents"""

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096
    ):
        self.model = model or settings.claude_model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._llm: Optional[ChatAnthropic] = None

    @property
    def llm(self) -> ChatAnthropic:
        """Lazy initialization of LLM"""
        if self._llm is None:
            self._llm = ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=settings.anthropic_api_key
            )
        return self._llm

    def create_chain(
        self,
        prompt_template: str,
        output_parser: Optional[Any] = None
    ) -> RunnableSequence:
        """Create a chain with prompt and optional parser"""
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = prompt | self.llm
        if output_parser:
            chain = chain | output_parser
        return chain

    def create_json_chain(
        self,
        prompt_template: str,
        pydantic_model: Optional[type[BaseModel]] = None
    ) -> RunnableSequence:
        """Create a chain that outputs JSON"""
        parser = JsonOutputParser(pydantic_object=pydantic_model) if pydantic_model else JsonOutputParser()
        return self.create_chain(prompt_template, parser)
