# AbiaHub Reports API Documentation

## Base URL
`https://api.abiahub.com/api/v1/`

## Authentication
All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### Reports

#### List Reports
```http
GET /reports/
```

Query Parameters:
- `page`: Page number (default: 1)
- `page_size`: Results per page (default: 20, max: 100)
- `status`: Filter by status (PENDING, VERIFIED, IN_PROGRESS, RESOLVED, REJECTED)
- `category`: Filter by category (INFRASTRUCTURE, SECURITY, etc.)
- `location`: Filter by location ID

Response:
```json
{
    "count": 123,
    "next": "http://api.abiahub.com/api/v1/reports/?page=2",
    "previous": null,
    "results": [
        {
            "id": "uuid",
            "title": "Report Title",
            "description": "Report description",
            "category": "INFRASTRUCTURE",
            "priority": "HIGH",
            "status": "PENDING",
            "location": {
                "type": "Point",
                "coordinates": [7.0, 5.0]
            },
            "address": "123 Street",
            "images": ["url1", "url2"],
            "videos": ["url1"],
            "voice_notes": ["url1"],
            "reporter_name": "John Doe",
            "created_at": "2024-03-20T10:30:00Z",
            "updated_at": "2024-03-20T10:30:00Z",
            "is_anonymous": false,
            "upvotes": 5
        }
    ]
}
```

#### Create Report
```http
POST /reports/
```

Request Body:
```json
{
    "title": "Report Title",
    "description": "Detailed description",
    "category": "INFRASTRUCTURE",
    "location": {
        "type": "Point",
        "coordinates": [7.0, 5.0]
    },
    "address": "123 Street",
    "lga": "lga_id",
    "is_anonymous": false,
    "images": ["file1", "file2"],
    "videos": ["file1"],
    "voice_notes": ["file1"]
}
```

Response: Same as single report object

#### Get Report Detail
```http
GET /reports/{id}/
```

Response: Same as single report object

#### Update Report Status
```http
PATCH /reports/{id}/
```

Request Body:
```json
{
    "status": "IN_PROGRESS"
}
```

Response: Same as single report object

### Media Upload

#### Upload Image
```http
POST /reports/upload-image/
```
Content-Type: multipart/form-data

Request Body:
- `image`: Image file (max 5MB, jpg/png)

Response:
```json
{
    "url": "https://storage.abiahub.com/images/uuid.jpg"
}
```

#### Upload Video
```http
POST /reports/upload-video/
```
Content-Type: multipart/form-data

Request Body:
- `video`: Video file (max 50MB, mp4)

Response:
```json
{
    "url": "https://storage.abiahub.com/videos/uuid.mp4"
}
```

#### Upload Voice Note
```http
POST /reports/upload-voice/
```
Content-Type: multipart/form-data

Request Body:
- `audio`: Audio file (max 10MB, mp3/m4a)

Response:
```json
{
    "url": "https://storage.abiahub.com/audio/uuid.mp3"
}
```

### Verification

#### Verify NIN
```http
POST /verify/nin/
```

Request Body:
```json
{
    "nin": "12345678901",
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1990-01-01"
}
```

Response:
```json
{
    "verified": true,
    "message": "NIN verification successful"
}
```

### Payments

#### Initialize Payment
```http
POST /reports/{id}/initialize-payment/
```

Request Body:
```json
{
    "amount": 1000.00,
    "email": "user@example.com"
}
```

Response:
```json
{
    "payment_url": "https://flutterwave.com/pay/xyz",
    "reference": "ref_123"
}
```

#### Verify Payment
```http
POST /reports/{id}/verify-payment/
```

Request Body:
```json
{
    "reference": "ref_123"
}
```

Response:
```json
{
    "verified": true,
    "message": "Payment verified successfully"
}
```

### Error Responses

All endpoints return standard HTTP status codes:

- 200: Success
- 201: Created
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Server Error

Error Response Format:
```json
{
    "error": "Error message",
    "details": {
        "field": ["Error details"]
    }
}
```

## Rate Limiting

- Authenticated users: 60 requests/minute
- Anonymous users: 30 requests/minute
- Sustained rate: 1000 requests/day for authenticated, 500/day for anonymous

## File Upload Limits

- Images: 5MB max, jpg/png only
- Videos: 50MB max, mp4 only
- Voice Notes: 10MB max, mp3/m4a only

## Pagination

All list endpoints are paginated with these query parameters:
- `page`: Page number
- `page_size`: Results per page (default: 20, max: 100)

## Caching

- List endpoints are cached for 5 minutes
- Detail endpoints are cached for 1 minute
- Cache is invalidated on any write operation 