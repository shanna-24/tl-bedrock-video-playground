# TL-Video-Playground Architecture

This document provides a comprehensive overview of the TL-Video-Playground system architecture, including component interactions, data flow, and design decisions.

## Table of Contents

1. [System Overview](#system-overview)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Details](#component-details)
4. [Data Flow](#data-flow)
5. [Technology Stack](#technology-stack)
6. [Design Decisions](#design-decisions)
7. [Security Architecture](#security-architecture)
8. [Scalability and Performance](#scalability-and-performance)

## System Overview

TL-Video-Playground is a video archive search and analysis system that leverages TwelveLabs AI models (Marengo and Pegasus) through Amazon Bedrock. The system enables users to:

- **Index videos**: Upload and organize video content into searchable indexes
- **Search videos**: Use natural language queries to find specific video segments
- **Analyze videos**: Extract insights from video content using AI-powered analysis
- **Play videos**: Stream and view video content with timecode support

### Key Features

- ✅ Natural language video search
- ✅ AI-powered video analysis
- ✅ Multi-index organization (up to 3 indexes)
- ✅ Video streaming with timecode navigation
- ✅ Simple password authentication
- ✅ Production-ready AWS deployment
- ✅ Green/purple gradient UI design

## High-Level Architecture

The system follows a three-tier architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
│                    (React/Vite Frontend)                     │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS/REST API
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend API Layer                         │
│                   (Python/FastAPI)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │   Auth   │  │  Index   │  │  Search  │  │ Analysis │   │
│  │ Service  │  │ Manager  │  │ Service  │  │ Service  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│  ┌──────────┐  ┌──────────┐                                │
│  │  Video   │  │ Metadata │                                │
│  │ Service  │  │  Store   │                                │
│  └──────────┘  └──────────┘                                │
└────────────────────────┬────────────────────────────────────┘
                         │ AWS SDK (boto3)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   AWS Infrastructure                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Bedrock    │  │      S3      │  │  S3 Vectors  │     │
│  │ (Marengo +   │  │   (Videos)   │  │ (Embeddings) │     │
│  │  Pegasus)    │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### Frontend Layer

**Technology**: React 19 + Vite 7 + Tailwind CSS 4

**Components**:

1. **Authentication**
   - `Login.tsx`: Password-based login form
   - `useAuth.ts`: Authentication state management

2. **Index Management**
   - `IndexList.tsx`: Display and manage indexes
   - `IndexCreate.tsx`: Create new indexes
   - `useIndexes.ts`: Index state and API calls

3. **Video Management**
   - `VideoUpload.tsx`: Drag-and-drop video upload
   - `VideoList.tsx`: Display videos in selected index
   - `VideoPlayer.tsx`: HTML5 video player with controls

4. **Search**
   - `SearchBar.tsx`: Natural language query input
   - `SearchResults.tsx`: Display search results with clips
   - `useSearch.ts`: Search state management

5. **Analysis**
   - `AnalysisForm.tsx`: Query input with scope selector
   - `AnalysisResults.tsx`: Display analysis insights

**Styling**: Green and purple gradient color scheme with Tailwind CSS

**State Management**: React Context API + custom hooks

**API Communication**: Axios for HTTP requests

### Backend Layer

**Technology**: Python 3.11 + FastAPI

**Modules**:

1. **API Endpoints** (`src/api/`)
   - `auth.py`: Authentication endpoints (login, logout)
   - `indexes.py`: Index management endpoints
   - `videos.py`: Video upload and streaming endpoints
   - `search.py`: Video search endpoint
   - `analysis.py`: Video analysis endpoints

2. **Services** (`src/services/`)
   - `auth_service.py`: Password verification, JWT tokens
   - `index_manager.py`: Index lifecycle, video management
   - `video_service.py`: Video upload, streaming URLs
   - `search_service.py`: Query embedding, similarity search
   - `analysis_service.py`: Video analysis with Pegasus

3. **AWS Clients** (`src/aws/`)
   - `bedrock_client.py`: Bedrock model invocation
   - `s3_client.py`: S3 operations (upload, download, presigned URLs)
   - `s3_vectors_client.py`: Vector storage and similarity search

4. **Storage** (`src/storage/`)
   - `metadata_store.py`: JSON-based index metadata persistence

5. **Models** (`src/models/`)
   - Pydantic models for Index, Video, VideoClip, SearchResults, AnalysisResult

6. **Configuration** (`src/config.py`)
   - Load and validate configuration from YAML files

### Infrastructure Layer

**AWS Services**:

1. **Amazon Bedrock**
   - **Marengo Model**: Video indexing and search
   - **Pegasus Model**: Video content analysis
   - Accessed via AWS SDK (boto3)

2. **Amazon S3**
   - **Video Bucket**: Original video file storage
   - **Metadata Bucket**: Index metadata persistence
   - Lifecycle policies for cost optimization

3. **Bedrock S3 Vectors**
   - Vector database for video embeddings
   - Similarity search for natural language queries

4. **ECS Fargate** (Production)
   - Containerized backend deployment
   - Auto-scaling based on CPU/memory
   - 2-10 tasks for high availability

5. **Application Load Balancer** (Production)
   - HTTPS traffic routing
   - Health checks
   - SSL termination

6. **CloudFront** (Production)
   - Global CDN for frontend
   - HTTPS enforcement
   - Cache optimization

## Data Flow

### Index Creation Flow

```
User → Frontend → Backend API → Index Manager
                                      ↓
                                 Bedrock (Marengo)
                                      ↓
                                 S3 Vectors (create collection)
                                      ↓
                                 Metadata Store (persist)
                                      ↓
Backend API → Frontend → User (index created)
```

**Steps**:
1. User submits index name via frontend
2. Backend validates index limit (max 3)
3. Backend invokes Marengo to create index
4. Bedrock creates vector collection in S3 Vectors
5. Backend persists index metadata locally
6. Frontend displays new index

### Video Upload Flow

```
User → Frontend (file) → Backend API → Video Service
                                            ↓
                                       S3 (upload video)
                                            ↓
                                       Index Manager
                                            ↓
                                       Bedrock (Marengo - generate embeddings)
                                            ↓
                                       S3 Vectors (store embeddings)
                                            ↓
                                       Metadata Store (update index)
                                            ↓
Backend API → Frontend → User (video added)
```

**Steps**:
1. User selects video file via drag-and-drop
2. Frontend uploads file to backend
3. Backend uploads video to S3
4. Backend invokes Marengo to generate embeddings
5. Embeddings stored in S3 Vectors
6. Index metadata updated with video info
7. Frontend displays video in list

### Video Search Flow

```
User → Frontend (query) → Backend API → Search Service
                                             ↓
                                        Bedrock (Marengo - embed query)
                                             ↓
                                        S3 Vectors (similarity search)
                                             ↓
                                        Video Service (generate presigned URLs)
                                             ↓
                                        Search Service (generate screenshots)
                                             ↓
Backend API → Frontend → User (search results with clips)
```

**Steps**:
1. User enters natural language query
2. Backend embeds query using Marengo
3. Backend performs similarity search in S3 Vectors
4. Backend generates presigned URLs for video clips
5. Backend generates screenshots for clips
6. Frontend displays results with thumbnails and timecodes
7. User clicks clip to play video at specific timecode

### Video Analysis Flow

```
User → Frontend (query + scope) → Backend API → Analysis Service
                                                      ↓
                                                 S3 (get video URIs)
                                                      ↓
                                                 Bedrock (Pegasus - analyze)
                                                      ↓
                                                 Format results
                                                      ↓
Backend API → Frontend → User (analysis insights)
```

**Steps**:
1. User enters analysis query and selects scope (index or video)
2. Backend retrieves video URIs from S3
3. Backend invokes Pegasus with query and video URIs
4. Pegasus analyzes video content and returns insights
5. Backend formats results into structured response
6. Frontend displays insights in readable format

### Authentication Flow

```
User → Frontend (password) → Backend API → Auth Service
                                                ↓
                                           Verify password hash
                                                ↓
                                           Generate JWT token
                                                ↓
Backend API → Frontend (token) → User (authenticated)
                                      ↓
                                 Store token in localStorage
                                      ↓
                            Include token in all API requests
```

**Steps**:
1. User enters password
2. Backend verifies password against bcrypt hash
3. Backend generates JWT token
4. Frontend stores token in localStorage
5. Frontend includes token in Authorization header for all requests
6. Backend validates token on protected endpoints

## Technology Stack

### Frontend

| Technology | Purpose | Version |
|------------|---------|---------|
| React | UI framework | 19.x |
| Vite | Build tool | 7.x |
| Tailwind CSS | Styling | 4.x |
| TypeScript | Type safety | 5.9+ |
| Axios | HTTP client | 1.x |
| React Router | Routing | 6.x |
| Vitest | Testing | 1.x |

### Backend

| Technology | Purpose | Version |
|------------|---------|---------|
| Python | Language | 3.11+ |
| FastAPI | Web framework | 0.100+ |
| boto3 | AWS SDK | 1.28+ |
| Pydantic | Data validation | 2.x |
| passlib | Password hashing | 1.7+ |
| PyJWT | JWT tokens | 2.8+ |
| pytest | Testing | 7.x |
| hypothesis | Property testing | 6.x |
| opencv-python | Video processing | 4.x |

### Infrastructure

| Service | Purpose |
|---------|---------|
| Amazon Bedrock | AI model access (Marengo, Pegasus) |
| Amazon S3 | Video and metadata storage |
| Bedrock S3 Vectors | Vector database for embeddings |
| ECS Fargate | Container hosting |
| Application Load Balancer | Traffic routing |
| CloudFront | CDN |
| ECR | Container registry |
| Secrets Manager | Secret storage |
| CloudWatch | Logging and monitoring |

### Development Tools

| Tool | Purpose |
|------|---------|
| Docker | Containerization |
| Docker Compose | Local development |
| LocalStack | AWS service mocking |
| AWS CDK | Infrastructure as code |
| Git | Version control |

## Design Decisions

### 1. Three-Tier Architecture

**Decision**: Separate frontend, backend, and infrastructure layers

**Rationale**:
- Clear separation of concerns
- Independent scaling of each layer
- Easier testing and maintenance
- Technology flexibility (can swap frontend/backend independently)

### 2. FastAPI for Backend

**Decision**: Use FastAPI instead of Flask or Django

**Rationale**:
- Native async/await support for non-blocking I/O
- Automatic API documentation (Swagger/OpenAPI)
- Type hints and validation with Pydantic
- High performance (comparable to Node.js)
- Modern Python features

### 3. React + Vite for Frontend

**Decision**: Use React with Vite instead of Create React App or Next.js

**Rationale**:
- Fast development server with HMR
- Optimized production builds
- Simple configuration
- No server-side rendering needed (SPA is sufficient)
- Modern tooling (ES modules, native TypeScript)

### 4. Tailwind CSS for Styling

**Decision**: Use Tailwind CSS instead of CSS-in-JS or traditional CSS

**Rationale**:
- Utility-first approach for rapid development
- Consistent design system
- Small production bundle (unused styles purged)
- Easy to implement green/purple gradient theme
- No runtime overhead

### 5. JSON File for Metadata Storage

**Decision**: Use local JSON file instead of database for index metadata

**Rationale**:
- Simple implementation for MVP
- No database setup required
- Easy to backup and restore
- Sufficient for small number of indexes (max 3)
- Can migrate to DynamoDB later if needed

### 6. JWT for Authentication

**Decision**: Use JWT tokens instead of session-based auth

**Rationale**:
- Stateless authentication (no server-side session storage)
- Works well with distributed systems (multiple ECS tasks)
- Easy to implement with FastAPI
- Can include user claims in token
- Standard and well-supported

### 7. ECS Fargate for Backend Hosting

**Decision**: Use ECS Fargate instead of EC2 or Lambda

**Rationale**:
- Serverless container hosting (no server management)
- Auto-scaling based on demand
- Better for long-running processes than Lambda
- More control than Lambda (custom runtime, dependencies)
- Cost-effective for moderate traffic

### 8. CloudFront for Frontend Hosting

**Decision**: Use S3 + CloudFront instead of Amplify or Vercel

**Rationale**:
- Full control over infrastructure
- Global CDN for low latency
- HTTPS by default
- Cost-effective for static content
- Integrates well with AWS ecosystem

### 9. Property-Based Testing

**Decision**: Use property-based tests in addition to unit tests

**Rationale**:
- Verify universal properties across all inputs
- Catch edge cases that unit tests miss
- Formal verification of correctness properties
- Complements example-based unit tests
- Industry best practice for critical systems

### 10. AWS CDK for Infrastructure

**Decision**: Use AWS CDK instead of CloudFormation or Terraform

**Rationale**:
- Infrastructure as code in Python (same language as backend)
- Type-safe infrastructure definitions
- Reusable constructs
- Automatic CloudFormation generation
- Better abstraction than raw CloudFormation

## Security Architecture

### Authentication and Authorization

1. **Password Authentication**
   - Bcrypt hashing with cost factor 12
   - Passwords never stored in plaintext
   - JWT tokens for session management
   - Token expiration (24 hours)

2. **API Security**
   - All endpoints require authentication (except login)
   - JWT token validation on every request
   - Input validation with Pydantic
   - Rate limiting (recommended for production)

### Network Security

1. **Production Deployment**
   - ECS tasks in private subnets (no direct internet access)
   - ALB in public subnets (HTTPS only)
   - Security groups restrict traffic flow
   - VPC isolation

2. **Data in Transit**
   - HTTPS for all frontend-backend communication
   - TLS for all AWS service calls
   - Presigned URLs for secure S3 access

### Data Security

1. **Encryption at Rest**
   - S3 buckets use server-side encryption (SSE-S3)
   - Secrets Manager encrypts secrets with KMS
   - EBS volumes encrypted (ECS Fargate default)

2. **Access Control**
   - IAM roles with least privilege
   - S3 buckets block public access
   - CloudFront OAI for S3 access
   - No hardcoded credentials

### Application Security

1. **Input Validation**
   - Pydantic models validate all inputs
   - File type and size validation
   - Query length limits
   - Index name validation

2. **Error Handling**
   - No sensitive information in error messages
   - Graceful degradation
   - Proper HTTP status codes
   - Logging for debugging

## Scalability and Performance

### Horizontal Scaling

1. **Backend**
   - ECS auto-scaling (2-10 tasks)
   - Stateless design (no local state)
   - Load balancing across tasks
   - Can scale to hundreds of tasks if needed

2. **Frontend**
   - CloudFront edge locations worldwide
   - S3 scales automatically
   - No server-side rendering (static files)

### Vertical Scaling

1. **ECS Task Size**
   - Current: 0.5 vCPU, 1 GB memory
   - Can increase to 4 vCPU, 30 GB memory
   - Adjust based on workload

### Caching

1. **CloudFront**
   - Cache static assets (JS, CSS, images)
   - TTL: 1 hour for HTML, 1 year for assets
   - Cache invalidation on deployment

2. **Application-Level** (Future Enhancement)
   - Cache search results
   - Cache embeddings
   - Redis for distributed caching

### Performance Optimizations

1. **Frontend**
   - Code splitting (Vite automatic)
   - Lazy loading of components
   - Image optimization
   - Minification and compression

2. **Backend**
   - Async/await for non-blocking I/O
   - Connection pooling for AWS clients
   - Batch operations where possible
   - Efficient video processing

3. **Database** (Future Enhancement)
   - Index metadata in DynamoDB for faster queries
   - ElastiCache for caching
   - Read replicas for high read throughput

### Monitoring and Observability

1. **Logging**
   - CloudWatch Logs for all backend logs
   - Structured logging (JSON format)
   - Log retention: 7 days (configurable)

2. **Metrics**
   - CloudWatch metrics for ECS, ALB, CloudFront
   - Container Insights for detailed ECS metrics
   - Custom metrics for business logic

3. **Tracing** (Future Enhancement)
   - AWS X-Ray for distributed tracing
   - Request ID propagation
   - Performance bottleneck identification

4. **Alerting**
   - CloudWatch Alarms for high CPU/memory
   - SNS notifications for critical issues
   - Budget alerts for cost control

## Future Enhancements

### Short-Term (1-3 months)

1. **User Management**
   - Multiple user accounts
   - Role-based access control
   - User-specific indexes

2. **Advanced Search**
   - Filters (date, duration, relevance)
   - Search history
   - Saved searches

3. **Video Management**
   - Video deletion
   - Video metadata editing
   - Thumbnail customization

### Medium-Term (3-6 months)

1. **Performance**
   - Redis caching layer
   - DynamoDB for metadata
   - Batch video processing

2. **Features**
   - Video transcription
   - Multi-language support
   - Export search results

3. **Monitoring**
   - AWS X-Ray tracing
   - Custom dashboards
   - Automated alerts

### Long-Term (6-12 months)

1. **Scalability**
   - Multi-region deployment
   - Global load balancing
   - Edge computing with Lambda@Edge

2. **Advanced AI**
   - Custom model fine-tuning
   - Real-time video analysis
   - Automated tagging

3. **Enterprise Features**
   - SSO integration
   - Audit logging
   - Compliance reporting

## Conclusion

TL-Video-Playground is designed as a production-ready, scalable video archive system with clear architectural boundaries, modern technology choices, and AWS best practices. The three-tier architecture provides flexibility for future enhancements while maintaining simplicity for the current feature set.

Key architectural strengths:
- ✅ Clear separation of concerns
- ✅ Stateless, horizontally scalable backend
- ✅ Global CDN for frontend
- ✅ Secure by default
- ✅ Cost-optimized for moderate usage
- ✅ Comprehensive testing strategy
- ✅ Infrastructure as code

For more information:
- [Local Setup Guide](./LOCAL_SETUP.md)
- [AWS Deployment Guide](./AWS_DEPLOYMENT.md)
- [Project README](../README.md)
