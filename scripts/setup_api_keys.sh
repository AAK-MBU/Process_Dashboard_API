echo "Setting up API keys in Docker container..."

python scripts/docker_setup_api_keys.py

if [ $? -eq 0 ]; then
    echo "API key setup completed successfully!"
    
    if [ -f /tmp/api_key.txt ]; then
        echo ""
        echo "API Key Details:"
        cat /tmp/api_key.txt
        echo ""
        echo "Save this information securely!"
    fi
else
    echo "API key setup failed!"
    exit 1
fi