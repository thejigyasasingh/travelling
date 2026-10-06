# Admin OpenAPI

This folder contains an OpenAPI (Swagger) YAML describing the admin panel API used by the admin frontend.

Files
- `admin_openapi.yaml` — OpenAPI 3.0.3 document for admin endpoints (paths under `/api/v1/admin`).

Serve locally with Swagger UI

1. Install `swagger-ui` (npm) or use the official [Swagger UI Docker image].

Using `swagger-ui` npm package (quick):

```bash
npx http-server -c-1 . -p 8000
# then open Swagger UI and paste the raw URL to admin_openapi.yaml
```

Using Docker (recommended):

```bash
docker run --rm -p 8080:8080 -e SWAGGER_JSON=/tmp/admin_openapi.yaml -v "$(pwd)/admin_openapi.yaml:/tmp/admin_openapi.yaml" swaggerapi/swagger-ui
```

Or integrate directly into your admin frontend by mounting this file into a Swagger UI instance or pointing your front-end's API client generator at the YAML file.

Replace the `servers` URL in the YAML with your actual API base URL before generating clients.
