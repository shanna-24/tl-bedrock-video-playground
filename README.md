# TwelveLabs on AWS Bedrock 🎥

A video archive search and analysis system powered by TwelveLabs AI models (Marengo and Pegasus) through Amazon Bedrock.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![React](https://img.shields.io/badge/react-19.x-blue.svg)
![AWS](https://img.shields.io/badge/AWS-Bedrock-orange.svg)

## ✨ Features

### 🎯 Core Capabilities

- **Natural Language Video Search**: Find specific video segments using conversational queries
- **Image-Based Search**: Upload images to find visually similar video moments
- **Multimodal Search**: Combine text and images for precise results
- **Modality Filtering**: Filter search results by visual, audio, or text content
- **AI-Powered Analysis**: Extract insights from video content with Pegasus model
- **Video Compliance Analysis**: Automated content compliance checking with configurable rules
- **Jockey Orchestration**: Advanced multi-video RAG analysis using Claude for complex index-level queries
- **Web Search Enrichment**: Augment video insights with current web information
- **Multi-Index Organization**: Organize videos into up to 5 searchable indexes
- **Video Streaming**: Play videos with timecode navigation and custom controls
- **Simple Authentication**: Password-based access control with JWT tokens
- **Automatic Embedding Processing**: Background job processor monitors and completes video embedding tasks

### 🎨 User Experience

- **Modern UI**: React 19 with Vite and Tailwind CSS
- **Green/Purple Gradient Theme**: Beautiful, consistent design
- **Drag-and-Drop Upload**: Easy video file management
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Search**: Fast, accurate results with relevance scoring

### 🏗️ Production Ready

- **AWS Deployment**: ECS Fargate, CloudFront, S3, Bedrock
- **Auto-Scaling**: Handles variable load automatically
- **Secure by Default**: Encryption, IAM roles, private subnets
- **Comprehensive Testing**: 800+ tests including property-based tests
- **Infrastructure as Code**: AWS CDK for reproducible deployments
- **Background Job Processing**: Automatic embedding retrieval and indexing with retry logic

## 🚀 Quick Start

### Docker Container

For the quickest setup, run from a pre-built Docker container:

```bash
docker run -d --name tl-video-playground \
  -p 8000:8000 \
  -e AWS_ACCESS_KEY_ID="your-key" \
  -e AWS_SECRET_ACCESS_KEY="your-secret" \
  -e AWS_REGION="us-east-1" \
  -v $(pwd)/config.yaml:/app/config.yaml:ro \
  tl-video-playground:latest
```

See the [Docker Quickstart Guide](docs/DOCKER_QUICKSTART.md) for complete instructions.

### Desktop Application (Electron)

For a standalone desktop app experience, see the [Electron Desktop App Guide](docs/ELECTRON_DESKTOP_APP.md).

```bash
# Development mode
./scripts/dev-electron.sh

# Build for production
./scripts/package-electron.sh
```

The desktop app bundles both frontend and backend into a single installable application for macOS, Windows, and Linux.

### Prerequisites

- Python 3.11+
- Node.js 20+
- AWS account with Bedrock access
- AWS CLI configured

### Local Development

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd tl-video-playground
   ```

2. **Configure AWS credentials**
   ```bash
   aws configure
   # Enter your AWS Access Key ID, Secret Access Key, and region
   ```

3. **Configure the application**
   ```bash
   cp config.example.yaml config.local.yaml
   # Edit config.local.yaml with your AWS settings and password hash
   ```
   
   See the [Configuration Guide](backend/CONFIG.md) for detailed information about all configuration options.

4. **Start the backend**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   export PYTHONPATH=src
   CONFIG_PATH=../config.local.yaml uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Start the frontend** (in a new terminal)
   ```bash
   cd frontend
   npm install
   echo "VITE_API_URL=http://localhost:8000" > .env
   npm run dev
   ```

6. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

For detailed setup instructions, see [Local Setup Guide](docs/LOCAL_SETUP.md).

### Production Deployment

Deploy to AWS with CDK:

```bash
cd infrastructure/cdk
cdk deploy --all
```

For complete deployment instructions, see [AWS Deployment Guide](docs/AWS_DEPLOYMENT.md).

## 📚 Documentation

- **[Local Setup Guide](docs/LOCAL_SETUP.md)**: Run the system locally for development
- **[Docker Quickstart](docs/DOCKER_QUICKSTART.md)**: Run from a pre-built Docker container
- **[Electron Desktop App](docs/ELECTRON_DESKTOP_APP.md)**: Build and distribute as a desktop application
- **[AWS Deployment Guide](docs/AWS_DEPLOYMENT.md)**: Deploy to production AWS infrastructure
- **[Architecture Overview](docs/ARCHITECTURE.md)**: System design and component interactions
- **[Backend API Guide](docs/BACKEND_API_GUIDE.md)**: Complete REST API reference
- **[Configuration Guide](backend/CONFIG.md)**: Detailed configuration options and tuning guide
- **[Jockey Configuration](docs/JOCKEY_CONFIG_PARAMETERS.md)**: Advanced multi-video RAG orchestration settings
- **[Search Modality Filtering](docs/SEARCH_MODALITY_FILTERING.md)**: Filter search by visual, audio, or text modalities

## 🏛️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Browser (React)                      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS/REST API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                Backend API (Python/FastAPI)                  │
│  Auth • Index Manager • Search • Analysis • Video Service   │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │      Background Embedding Job Processor             │   │
│  │  Monitors async jobs • Retrieves embeddings         │   │
│  │  Stores in S3 Vectors • Processes segments          │   │
│  │  (transcription + thumbnails in one pass)           │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────┘
                         │ AWS SDK
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   AWS Infrastructure                         │
│  Bedrock (Marengo + Pegasus) • S3 • S3 Vectors             │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

- **Frontend**: React 19 + Vite + Tailwind CSS
- **Backend**: Python 3.11 + FastAPI + boto3
- **AI Models**: TwelveLabs Marengo (search) + Pegasus (analysis)
- **Storage**: Amazon S3 (videos) + Bedrock S3 Vectors (embeddings)
- **Hosting**: ECS Fargate (backend) + CloudFront (frontend)
- **Background Processing**: Embedding job processor with automatic retry logic
- **Jockey Orchestration**: Multi-video RAG analysis with Claude for complex queries

### Embedding Job Processing Flow

When you upload a video, the system follows this workflow:

```
1. Video Upload
   └─> Start async Bedrock embedding job
       └─> Store job record in job store
           └─> Return immediately to user

2. Background Processor (runs every 30s)
   └─> Poll pending jobs
       └─> Check job status with Bedrock
           ├─> If InProgress: Update status, continue polling
           ├─> If Completed: 
           │   └─> Retrieve embeddings from S3
           │       └─> Store in S3 Vectors for search
           │           └─> Process all segments (unified pass):
           │               • Download video once
           │               • For each segment:
           │                 - Extract segment
           │                 - Generate thumbnail
           │                 - Transcribe with Pegasus
           │               └─> Mark job complete
           └─> If Failed:
               └─> Retry with exponential backoff (max 3 retries)
                   └─> Mark permanently failed if max retries exceeded

3. Video Becomes Searchable
   └─> Embeddings indexed in S3 Vectors
       └─> Search queries return results
           └─> Thumbnails served from S3 cache (pre-generated)
```

**Key Features:**
- **Asynchronous Processing**: Videos are searchable within 5 minutes of upload
- **Automatic Retries**: Failed jobs retry with exponential backoff (60s, 120s, 240s)
- **Concurrent Processing**: Handles up to 5 jobs simultaneously
- **Restart Resilience**: Jobs persist across server restarts
- **Idempotent Storage**: Duplicate embeddings are prevented
- **Unified Segment Processing**: Transcriptions and thumbnails generated in one pass
- **Efficient Resource Usage**: Single video download for all segment operations
- **Fast Search Results**: Thumbnails and transcriptions served from S3 cache
- **Comprehensive Logging**: All job events logged for debugging

**Configuration:**
The processor behavior can be tuned in `config.yaml`:
```yaml
embedding_processor:
  enabled: true              # Enable/disable processor
  polling_interval: 30       # Seconds between job checks
  max_concurrent_jobs: 5     # Parallel job limit
  max_retries: 3             # Retry attempts before permanent failure
  retry_backoff_base: 2      # Exponential backoff base (delay = base^retry minutes)
```

See the [Configuration Guide](backend/CONFIG.md) for detailed tuning options.

### Compliance Analysis Flow

The compliance system analyzes videos against configurable rules to identify content issues:

```
1. Content Relevance Pre-Check (Optional)
   └─> Lexical search on video transcription
       └─> If product/brand not mentioned → BLOCK as irrelevant
       └─> If mentioned → Continue to full analysis

2. Pegasus AI Analysis
   └─> Analyze entire video against compliance categories:
       ├─> Moral Standards (hate speech, illegal behavior, profanity, danger)
       ├─> Video Content (suitability, brand exclusivity, product focus, tone)
       └─> Custom categories (configurable)

3. Issue Detection
   └─> For each issue found:
       ├─> Extract timecode location
       ├─> Generate thumbnail at issue timestamp
       ├─> Assign status (BLOCK or REVIEW)
       └─> Provide detailed description

4. Overall Status Computation
   └─> BLOCK: Any blocking issue found
   └─> REVIEW: Review issues but no blocking issues
   └─> PASS: No issues detected
```

**Configuration Files** (stored in S3 at `compliance/configuration/`):
- `compliance_params.json` - Company, category, and product line settings
- `moral_standards_check.json` - Moral/ethical compliance rules
- `video_content_check.json` - Content quality and brand compliance rules
- `content_relevance_check.json` - Pre-screening configuration

For detailed architecture, see [Architecture Documentation](docs/ARCHITECTURE.md).

## 🎯 Use Cases

### Video Archive Management
- Upload and organize video content into searchable indexes
- Manage up to 5 indexes with unlimited videos per index
- Persistent storage across sessions

### Content Discovery
- Search for specific scenes using natural language
- Find relevant video segments with timecode precision
- View search results with screenshots and relevance scores

### Video Analysis
- Ask questions about video content
- Extract insights without watching entire videos
- Analyze entire indexes or individual videos

### Video Playback
- Stream videos directly from S3
- Navigate to specific timecodes from search results
- Standard playback controls (play, pause, seek)

### Video Compliance Analysis
- Automated content compliance checking using Pegasus AI
- Configurable compliance rules via JSON configuration files
- Pre-screening with content relevance checks (lexical search)
- Multi-category analysis: moral standards, video content quality, brand compliance
- Issue detection with timecode precision and auto-generated thumbnails
- Three-tier status system: PASS, REVIEW (needs human review), BLOCK (auto-reject)
- Customizable for different brands, products, and compliance requirements

## 🧪 Testing

The project includes comprehensive testing:

### Backend Tests (800+ tests)

```bash
cd backend

# Run all tests
pytest

# Run unit tests
pytest tests/unit/

# Run property-based tests
pytest tests/property/

# Run with coverage
pytest --cov=src --cov-report=html
```

### Frontend Tests

```bash
cd frontend

# Run all tests
npm test

# Run with coverage
npm run test:coverage
```

### Test Coverage

- **Unit Tests**: Specific examples and edge cases
- **Property-Based Tests**: Universal properties across all inputs
- **Integration Tests**: End-to-end API flows
- **Component Tests**: React component rendering and interactions

## 🛠️ Technology Stack

### Frontend
- React 19
- Vite 7
- Tailwind CSS 4
- TypeScript 5.9
- Axios
- Vitest

### Backend
- Python 3.11
- FastAPI
- boto3 (AWS SDK)
- Pydantic
- pytest + hypothesis
- passlib + PyJWT

### Infrastructure
- Amazon Bedrock
- Amazon S3
- Bedrock S3 Vectors
- ECS Fargate
- Application Load Balancer
- CloudFront
- AWS CDK

## 📁 Project Structure

```
tl-video-playground/
├── backend/              # Python FastAPI backend
│   ├── src/             # Source code
│   │   ├── api/         # API endpoints
│   │   ├── services/    # Business logic
│   │   │   ├── embedding_job_store.py      # Job persistence
│   │   │   ├── embedding_job_processor.py  # Background worker
│   │   │   ├── embedding_retriever.py      # S3 embedding retrieval
│   │   │   ├── embedding_indexer.py        # S3 Vectors storage
│   │   │   ├── segment_processor_service.py  # Unified transcription + thumbnails
│   │   │   └── websocket_manager.py        # Real-time updates
│   │   ├── models/      # Data models
│   │   ├── aws/         # AWS client wrappers
│   │   ├── orchestration/  # Jockey multi-video RAG orchestration
│   │   ├── storage/     # Metadata persistence
│   │   └── utils/       # Utility functions
│   └── tests/           # Unit, property, integration tests
├── frontend/            # React/Vite frontend
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── contexts/    # React context providers
│   │   ├── hooks/       # Custom React hooks
│   │   ├── services/    # API client
│   │   └── types/       # TypeScript types
│   ├── electron/        # Electron desktop app
│   └── public/          # Static assets
├── infrastructure/      # AWS CDK infrastructure
│   └── cdk/
│       ├── stacks/      # CDK stack definitions
│       └── app.py       # CDK app entry point
├── scripts/             # Development and utility scripts
├── docs/                # Documentation
│   ├── LOCAL_SETUP.md
│   ├── AWS_DEPLOYMENT.md
│   ├── ARCHITECTURE.md
│   ├── BACKEND_API_GUIDE.md
│   ├── ELECTRON_DESKTOP_APP.md
│   ├── JOCKEY_CONFIG_PARAMETERS.md
│   └── SEARCH_MODALITY_FILTERING.md
├── docker-compose.yml   # Local development setup
└── README.md           # This file
```

## 🔒 Security

- ✅ Password hashing with bcrypt
- ✅ JWT token authentication
- ✅ HTTPS enforcement
- ✅ S3 bucket encryption
- ✅ IAM roles with least privilege
- ✅ Private subnets for backend
- ✅ Secrets Manager for sensitive data
- ✅ Input validation on all endpoints

## 🎓 Learn More

- [Amazon Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [TwelveLabs AI Models](https://www.twelvelabs.io/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)

---

**Built with ❤️ using TwelveLabs AI, AWS Bedrock, and modern web technologies**
