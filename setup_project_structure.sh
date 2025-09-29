#!/bin/bash
# setup_project_structure.sh - Creates all directories and initial files

echo "🏗️ Creating Project Lyra directory structure..."

# Root structure
mkdir -p companion/{gateway,discord_bot,embedding_service}
mkdir -p companion/gateway/{routers,services,data_models,utils,security}
mkdir -p companion/discord_bot/{commands,utils}
mkdir -p companion/embedding_service
mkdir -p companion/database/migrations
mkdir -p companion/tests/{unit,integration,fixtures}
mkdir -p companion/scripts
mkdir -p companion/docs

# Create __init__.py files for Python packages
find companion -type d -exec touch {}/__init__.py \;

# Create initial configuration files
touch companion/.env.example
touch companion/docker-compose.yml
touch companion/Caddyfile
touch companion/requirements.txt

# Gateway service files
touch companion/gateway/{main.py,config.py,database.py}
touch companion/gateway/routers/{chat.py,memory.py,personality.py,admin.py,health.py}
touch companion/gateway/services/{letta_service.py,user_service.py,proactive_manager.py,reflection.py}
touch companion/gateway/data_models/{personality.py,memory.py,user.py,interaction.py}
touch companion/gateway/utils/{mmr.py,importance_scorer.py,scheduler.py,background.py,exceptions.py,discord_sender.py}
touch companion/gateway/security/{semantic_injection_detector.py,defensive_response.py}

# Discord bot files
touch companion/discord_bot/{bot.py,commands.py,utils.py}

# Embedding service files
touch companion/embedding_service/{main.py,requirements.txt,Dockerfile}

# Database files
touch companion/database/migrations/{001_init.sql,002_personhood.sql,003_memory_conflicts.sql,004_user_profiles.sql,005_security.sql}

# Test files
touch companion/tests/conftest.py
touch companion/tests/unit/{test_personality_engine.py,test_memory_manager.py,test_letta_integration.py,test_security.py}
touch companion/tests/integration/test_full_conversation.py

# Scripts
touch companion/scripts/{backup.sh,monitor.sh,deploy.sh}

# Dockerfiles
touch companion/gateway/Dockerfile
touch companion/discord_bot/Dockerfile
touch companion/embedding_service/Dockerfile

echo "✅ Project structure created successfully!"
echo "📁 Total directories: $(find companion -type d | wc -l)"
echo "📄 Total files: $(find companion -type f | wc -l)"