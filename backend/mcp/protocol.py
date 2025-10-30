"""
MCP (Multi-Agent Communication Protocol) Base Implementation
Provides standardized communication protocol for agent coordination
"""
import json
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import uuid


class MCPMessageType(Enum):
    """MCP Message Types"""
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "publish"
    ERROR = "error"


class AgentType(Enum):
    """Available Agent Types"""
    TRANSCRIPTION = "transcription"
    VISION = "vision"
    GENERATION = "generation"
    ORCHESTRATOR = "orchestrator"


@dataclass
class MCPMessage:
    """Standard MCP Message Structure"""
    message_id: str
    timestamp: str
    source: AgentType
    target: Optional[AgentType]
    message_type: MCPMessageType
    method: str
    params: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return asdict(self)

    def to_json(self) -> str:
        """Serialize message to JSON"""
        # Convert enums to values for JSON serialization
        data = self.to_dict()
        data['message_type'] = self.message_type.value
        data['source'] = self.source.value
        if self.target:
            data['target'] = self.target.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, json_str: str) -> 'MCPMessage':
        """Deserialize message from JSON"""
        data = json.loads(json_str)
        data['message_type'] = MCPMessageType(data['message_type'])
        data['source'] = AgentType(data['source'])
        if data.get('target'):
            data['target'] = AgentType(data['target'])
        return cls(**data)


class MCPEndpoint:
    """Base class for MCP communication endpoints"""
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.subscribers: Dict[str, List[callable]] = {}
    
    async def send_message(
        self,
        target: AgentType,
        method: str,
        params: Dict[str, Any]
    ) -> MCPMessage:
        """Send a request message and wait for response"""
        message = MCPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            source=self.agent_type,
            target=target,
            message_type=MCPMessageType.REQUEST,
            method=method,
            params=params
        )
        
        # TO DO - Route to the target agent
        # For now, use a message bus pattern
        await self.message_queue.put(message)
        return message
    
    async def publish(
        self,
        method: str,
        params: Dict[str, Any]
    ) -> None:
        """Publish a notification to subscribers"""
        message = MCPMessage(
            message_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat(),
            source=self.agent_type,
            target=None,
            message_type=MCPMessageType.NOTIFICATION,
            method=method,
            params=params
        )
        await self.message_queue.put(message)
    
    async def handle_message(self, message: MCPMessage) -> MCPMessage:
        """Handle incoming message - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement handle_message")