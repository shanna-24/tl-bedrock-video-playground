# Local Development Setup

This guide will help you set up and run the TL-Video-Playground system on your local machine for development purposes.

## Prerequisites

Before you begin, ensure you have the following installed on your system:

### Required Software

1. **Python 3.11+**
   - Download from [python.org](https://www.python.org/downloads/)
   - Verify installation: `python --version`

2. **Node.js 20+**
   - Download from [nodejs.org](https://nodejs.org/)
   - Verify installation: `node --version` and `npm --version`

3. **Git**
   - Download from [git-scm.com](https://git-scm.com/)
   - Verify installation: `git --version`

4. **AWS CLI**
   - Install: `pip install awscli`
   - Configure: `aws configure`

5. **AWS Account**
   - Active AWS account with appropriate permissions
   - Access to Amazon Bedrock (available in select regions)
   - Bedrock model access granted for TwelveLabs models

## Project Structure

```
tl-video-playground/
├── backend/              # Python FastAPI backend
│   ├── src/             # Source code
│   ├── tests/           # Unit, property, and integration tests
│   ├── requirements.txt # Python dependencies
│   └── Dockerfile.dev   # Development Docker image
├── frontend/            # React/Vite frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   ├── package.json    # Node dependencies
│   └── Dockerfile.dev  # Development Docker image
├── docs/               # Documentation
├── data/               # Local data storage (created at runtime)
├── config.local.yaml   # Local configuration
├── docker-compose.yml  # Docker Compose configuration
└── README.md          # Project overview
```

## Setup Steps

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tl-video-playground
```

### 2. Configure AWS Credentials

```bash
# Configure AWS CLI with your credentials
aws configure

# You'll be prompted for:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region (e.g., us-east-1)
# - Default output format (json)
```

### 3. Create AWS Resources

#### Create S3 Bucket

```bash
# Create a bucket for video storage
aws s3 mb s3://your-tl-video-bucket --region us-east-1

# Enable versioning (optional but recommended)
aws s3api put-bucket-versioning \
  --bucket your-tl-video-bucket \
  --versioning-configuration Status=Enabled
```

#### Create S3 Vector Bucket

```bash
# IMPORTANT: This is required for index creation to work
aws s3vectors create-vector-bucket \
  --vector-bucket-name your-tl-video-bucket \
  --region us-east-1

# Verify it was created
aws s3vectors list-vector-buckets --region us-east-1
```

#### Request Bedrock Model Access

1. Go to the [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access** in the left sidebar
3. Click **Request model access** or **Manage model access**
4. Find and enable access to:
   - **TwelveLabs Marengo** (`twelvelabs.marengo-v1`) - for video indexing and search
   - **TwelveLabs Pegasus** (`twelvelabs.pegasus-v1`) - for video analysis
5. Submit the request (approval is usually instant for most models)
6. Wait for "Access granted" status

**Note:** TwelveLabs models may not be available in all regions. Check the [Bedrock model availability](https://docs.aws.amazon.com/bedrock/latest/userguide/models-regions.html) documentation.

### 4. Configure the Application

Copy the example configuration file and customize it:

```bash
cp config.prod.yaml.example config.local.yaml
```

Edit `config.local.yaml` with your settings:

```yaml
marengo_model_id: "twelvelabs.marengo-v1"
pegasus_model_id: "twelvelabs.pegasus-v1"
aws_region: "us-east-1"  # or your preferred region
s3_bucket_name: "your-tl-video-bucket"  # bucket you created
s3_vectors_collection: "video-embeddings"
max_indexes: 3
auth_password_hash: "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYIeWU2u3zu"  # password: "admin"
environment: "local"
```

**Note:** To generate a new password hash:

```bash
python -c "from passlib.hash import bcrypt; print(bcrypt.hash('your_password'))"
```

### 5. Start the Backend

### 5. Start the Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set Python path and start server
cd src
export PYTHONPATH=.
CONFIG_PATH=../../config.local.yaml uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend will be available at http://localhost:8000

### 6. Start the Frontend

Open a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# Run the frontend
npm run dev
```

Frontend will be available at http://localhost:5173

### 7. Verify the Setup

1. Start the backend and check logs for successful AWS connection
2. Access the API docs: http://localhost:8000/docs
3. Try logging in with your configured password
4. Create an index to verify Bedrock connectivity
5. Upload a test video to verify S3 connectivity

### 8. Compliance Configuration (Auto-loaded)

The compliance configuration files are automatically uploaded to S3 on first startup if they don't already exist. No manual action is required.

If you want to customize the compliance rules, edit the files in `backend/compliance_config/` before starting the backend, or manually upload custom configs:

```bash
# From the project root directory
./scripts/upload-compliance-config.sh your-bucket-name us-east-1
```

## Running Tests

### Backend Tests

```bash
cd backend

# Activate virtual environment
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run property-based tests only
pytest tests/property/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_auth_service.py

# Run with verbose output
pytest -v
```

### Frontend Tests

```bash
cd frontend

# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run specific test file
npm test -- SearchBar.test.tsx
```

## Development Workflow

### Making Changes

1. **Backend changes**: Edit files in `backend/src/`, the server will auto-reload
2. **Frontend changes**: Edit files in `frontend/src/`, the page will hot-reload
3. **Configuration changes**: Restart the services after editing `config.local.yaml`

### Adding Dependencies

**Backend:**
```bash
cd backend
source venv/bin/activate
pip install <package-name>
pip freeze > requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install <package-name>
```

### Database/Storage

- **Metadata**: Stored in `data/indexes.json` (created automatically)
- **Videos**: Stored in AWS S3
- **Embeddings**: Stored in AWS Bedrock S3 Vectors

## Troubleshooting

### Port Already in Use

If you see "port already in use" errors:

```bash
# Check what's using the port
lsof -i :8000  # Backend
lsof -i :5173  # Frontend

# Kill the process
kill -9 <PID>
```

### Backend Connection Errors

1. Verify AWS credentials are configured: `aws sts get-caller-identity`
2. Check configuration file exists: `ls -la config.local.yaml`
3. Verify S3 bucket exists: `aws s3 ls s3://your-bucket-name`
4. Check backend logs for detailed errors

### Frontend API Errors

1. Ensure backend is running: `curl http://localhost:8000/health`
2. Check CORS configuration in backend
3. Verify `.env` file has correct API URL
4. Check browser console for detailed errors

### Module Not Found Errors

**Backend:**
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### Permission Errors

On Linux/macOS, you may need to adjust permissions:

```bash
chmod -R 755 backend/
chmod -R 755 frontend/
chmod -R 755 data/
```

## Cost Considerations

Using AWS services will incur costs:

- **S3 Storage**: ~$0.023/GB/month
- **S3 Requests**: $0.0004 per 1,000 PUT requests, $0.0004 per 10,000 GET requests
- **Bedrock Marengo**: ~$0.05 per minute of video indexed
- **Bedrock Pegasus**: ~$0.10 per analysis request
- **Data Transfer**: First 100GB/month free, then $0.09/GB

**Estimated cost for testing** (10 videos, 5 minutes each, 10 searches, 5 analyses):
- S3: ~$0.50
- Bedrock: ~$3-5
- **Total: ~$5-10 for initial testing**

**Important:** Monitor your AWS billing dashboard and set up billing alerts to avoid unexpected charges.

## Troubleshooting AWS Connection

## Troubleshooting AWS Connection

**Error: "The specified vector bucket could not be found"**
- You need to create an S3 Vector Bucket first (see Step 3 above)
- Run: `aws s3vectors create-vector-bucket --vector-bucket-name your-bucket-name --region your-region`
- Verify it was created: `aws s3vectors list-vector-buckets --region your-region`

**Error: "Access Denied" when creating index**
- Verify Bedrock model access is granted in the console
- Check IAM permissions include `bedrock:InvokeModel`

**Error: "Bucket does not exist"**
- Verify the bucket name in `config.local.yaml` matches your S3 bucket
- Ensure the bucket is in the same region as specified in config

**Error: "Model not found"**
- Verify the model IDs are correct: `twelvelabs.marengo-v1` and `twelvelabs.pegasus-v1`
- Check that TwelveLabs models are available in your region

**Slow performance**
- This is normal for Bedrock models (video processing takes time)
- Marengo indexing: ~30-60 seconds per minute of video
- Pegasus analysis: ~10-30 seconds per request

## Next Steps

- Read [ARCHITECTURE.md](./ARCHITECTURE.md) to understand the system design
- Read [AWS_DEPLOYMENT.md](./AWS_DEPLOYMENT.md) for production deployment
- Check the [README.md](../README.md) for feature overview
- Explore the API documentation at http://localhost:8000/docs

## Getting Help

- Check the [GitHub Issues](https://github.com/your-repo/issues) for known problems
- Review the backend logs for detailed error messages
- Check AWS CloudWatch logs for service-specific issues

## Clean Up

To completely remove all local data:

```bash
# Remove local data
rm -rf data/

# Remove Python virtual environment
rm -rf backend/venv/

# Remove Node modules
rm -rf frontend/node_modules/
```
