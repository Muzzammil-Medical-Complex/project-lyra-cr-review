# AI Companion System

A sophisticated multi-user AI companion system with evolving personality, memory management, and proactive conversation capabilities.

## Overview

The AI Companion System is a production-ready platform that creates unique, evolving AI personalities for each user. Built with cutting-edge technologies, it provides:

- **Personality Modeling**: Big Five traits (fixed) + PAD emotional states (dynamic) + quirks/needs (evolving)
- **Memory System**: Episodic/Semantic memory with vector storage and MMR retrieval
- **Proactive Conversations**: AI-initiated conversations based on user needs and patterns
- **Security Framework**: Semantic injection detection and defensive responses
- **Discord Integration**: Full Discord bot with slash commands and proactive messaging

## Architecture

The system consists of 7 containerized microservices:

1. **PostgreSQL + pgvector**: User profiles, personality states, and interaction logs
2. **Qdrant**: Vector database for semantic memory storage and retrieval
3. **Redis**: Caching layer for performance optimization
4. **Letta**: Agent framework for stateful conversations
5. **Embedding Service**: Gemini API wrapper for text embeddings
6. **Gateway API**: Main FastAPI application orchestrating all services
7. **Discord Bot**: User interface with proactive messaging capabilities

## Key Features

### Personality System
- **Big Five Traits**: Fixed personality dimensions (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism)
- **PAD Emotional States**: Dynamic emotional dimensions (Pleasure, Arousal, Dominance) with 8 basic emotions
- **Quirks**: Behavioral patterns, speech quirks, and preferences that evolve through reinforcement
- **Psychological Needs**: Social, validation, intellectual, creative, and rest needs with decay mechanics

### Memory Management
- **Episodic Memory**: Specific events and conversations stored with importance scoring
- **Semantic Memory**: General knowledge and patterns extracted from episodic memories
- **MMR Retrieval**: Maximal Marginal Relevance algorithm for diverse, relevant memory retrieval
- **Memory Consolidation**: Nightly process that converts episodic memories to semantic knowledge

### Proactive Conversations
- **Multi-Factor Scoring**: Need urgency, timing optimization, and personality-based initiation
- **Personalized Starters**: AI-generated conversation openers based on user context
- **Opportunistic Timing**: Proactive messages initiated during optimal user engagement windows

### Security
- **Semantic Injection Detection**: AI-powered threat detection for role manipulation and system queries
- **Defensive Responses**: Personality-consistent defensive responses to security threats
- **Rate Limiting**: Protection against abuse with configurable limits
- **Incident Tracking**: Comprehensive logging of all security events

## Technology Stack

- **Primary LLM**: Chutes.ai (Qwen3-80B-A3B-Instruct)
- **Fast LLM**: Groq (Llama-4-Maverick) for scoring/security
- **Embeddings**: Gemini embedding-001 (1536-dim, cost-effective)
- **Agent Framework**: Letta 0.6.8 (stateful conversations)
- **API**: FastAPI 0.118.0 (async performance)
- **Database**: PostgreSQL 16.4 + pgvector 0.8.1
- **Vector Store**: Qdrant 1.12.1 (hybrid search)
- **Cache**: Redis 7.4.7+ (hot data, sessions)
- **Interface**: Discord.py 2.6.3
- **Containerization**: Docker + Compose

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+
- API keys for Chutes.ai, Groq, and Gemini

### Setup

1. **Clone the repository:**
```bash
git clone <repository-url>
cd project-lyra
```

2. **Configure environment variables:**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Build and start services:**
```bash
docker-compose up -d
```

4. **Initialize the database:**
```bash
# Run database migrations
docker-compose exec postgres psql -U companion -d companion_db -f /migrations/001_init.sql
# Continue with other migration files...
```

5. **Access the system:**
- Gateway API: `http://localhost:8000`
- Discord Bot: Invite to your server
- Health Check: `http://localhost:8000/health`

### Development

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run tests:**
```bash
pytest tests/
```

3. **Run specific service:**
```bash
cd gateway
uvicorn main:app --reload
```

## API Documentation

Detailed API documentation is available at `http://localhost:8000/docs` when the gateway is running.

See [API.md](docs/API.md) for comprehensive API documentation.

## Deployment

### Production Deployment

1. **Set environment to production:**
```bash
export ENVIRONMENT=production
```

2. **Configure domain and SSL:**
Update the `Caddyfile` with your domain and ensure DNS is configured.

3. **Deploy with Docker Compose:**
```bash
docker-compose -f docker-compose.yml up -d
```

### Monitoring and Maintenance

- **Health checks**: `http://your-domain.com/health`
- **Logs**: `docker-compose logs -f <service>`
- **Backups**: Use `scripts/backup.sh` for regular backups
- **Monitoring**: Use `scripts/monitor.sh` for system health monitoring

## Scripts

- `scripts/backup.sh`: Comprehensive backup and restore
- `scripts/monitor.sh`: Health monitoring and alerting
- `scripts/deploy.sh`: Production deployment automation

## Testing

The system includes comprehensive test suites:

- **Unit Tests**: Individual component testing
- **Integration Tests**: Service interaction testing
- **End-to-End Tests**: Complete conversation flow testing

Run tests with:
```bash
pytest tests/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue on the GitHub repository or contact the maintainers.

## Acknowledgments

- Thanks to the Letta team for the agent framework
- Thanks to the Qdrant team for the vector database
- Thanks to all contributors and the open-source community