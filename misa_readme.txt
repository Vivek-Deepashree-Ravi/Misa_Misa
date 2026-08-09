# Start and build all services
docker compose up --build

# Start in the background
docker compose up --build -d

# Check container status
docker compose ps

# Open Bash inside the Misa container
docker compose exec misa bash
# Or:
docker exec -it misa-app bash

# Check Ollama environment variables inside misa-app
env | grep OLLAMA

# Test connection from Misa to Ollama
python -c "import requests; print(requests.get('http://ollama:11434/api/tags').json())"

# Test the Flask application from inside misa-app
python -c "import requests; print(requests.get('http://localhost:8000').text)"

# Exit the container shell
exit

# View all logs
docker compose logs -f

# View model-download logs
docker compose logs -f model-pull

# Stop and remove the project containers
docker compose down

# Validate compose.yaml
docker compose config