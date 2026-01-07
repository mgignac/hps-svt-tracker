# Kubernetes Deployment Guide

This directory contains Kubernetes manifests for deploying the HPS SVT Tracker.

## Prerequisites

- Kubernetes cluster (1.21+)
- `kubectl` configured to access your cluster
- Container registry access (to push/pull images)
- Storage class available for PersistentVolumeClaim

## Quick Start

```bash
# 1. Create namespace
kubectl create namespace hps-svt-tracker

# 2. Create secret (IMPORTANT: use a secure key!)
kubectl create secret generic svt-tracker-secret \
  --from-literal=secret-key='$(openssl rand -hex 32)' \
  -n hps-svt-tracker

# 3. Build and push Docker image
docker build -t your-registry/hps-svt-tracker:v0.1.0 ..
docker push your-registry/hps-svt-tracker:v0.1.0

# 4. Update image reference in kustomization.yaml
#    Edit the images section with your registry path and tag

# 5. Deploy
kubectl apply -k . -n hps-svt-tracker

# 6. Verify deployment
kubectl get pods -n hps-svt-tracker
kubectl get svc -n hps-svt-tracker
```

## Accessing the Application

### Option 1: Port Forward (Development/Testing)
```bash
kubectl port-forward svc/svt-tracker 5000:80 -n hps-svt-tracker
# Access at http://localhost:5000
```

### Option 2: NodePort
Edit the Service in `deployment.yaml`:
```yaml
spec:
  type: NodePort
  ports:
    - name: http
      port: 80
      targetPort: http
      nodePort: 30500  # Choose a port in range 30000-32767
```

### Option 3: Ingress (Production)
Uncomment and configure the Ingress resource in `deployment.yaml`:
1. Set your domain in `spec.rules[0].host`
2. Configure TLS if needed
3. Ensure you have an Ingress controller installed (e.g., nginx-ingress)

## Configuration

### Environment Variables

Configured via ConfigMap (`svt-tracker-config`):

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | `production` | Flask environment |
| `SVT_DB_PATH` | `/data/db/svt_components.db` | Database file path |
| `SVT_DATA_DIR` | `/data/test_data` | Test data directory |
| `GUNICORN_WORKERS` | `2` | Number of gunicorn workers |
| `GUNICORN_THREADS` | `4` | Threads per worker |
| `GUNICORN_TIMEOUT` | `120` | Request timeout (seconds) |

### Secrets

| Secret | Key | Description |
|--------|-----|-------------|
| `svt-tracker-secret` | `secret-key` | Flask SECRET_KEY for sessions |

Generate a secure key:
```bash
openssl rand -hex 32
# or
python -c "import secrets; print(secrets.token_hex(32))"
```

### Storage

The PersistentVolumeClaim requests 10Gi by default. Adjust in `deployment.yaml`:
```yaml
spec:
  resources:
    requests:
      storage: 20Gi  # Increase as needed
```

If your cluster requires a specific storage class:
```yaml
spec:
  storageClassName: your-storage-class
```

## Management Commands

### View logs
```bash
kubectl logs -f deployment/svt-tracker -n hps-svt-tracker
```

### Shell into pod
```bash
kubectl exec -it deployment/svt-tracker -n hps-svt-tracker -- /bin/bash
```

### Check pod status
```bash
kubectl describe pod -l app=svt-tracker -n hps-svt-tracker
```

### Restart deployment
```bash
kubectl rollout restart deployment/svt-tracker -n hps-svt-tracker
```

### Scale (not recommended with SQLite)
```bash
# Only use 1 replica with SQLite!
kubectl scale deployment/svt-tracker --replicas=1 -n hps-svt-tracker
```

## Backup and Restore

### Backup database
```bash
# Create backup
kubectl exec deployment/svt-tracker -n hps-svt-tracker -- \
  tar czf - /data/db /data/test_data > svt-backup-$(date +%Y%m%d).tar.gz
```

### Restore database
```bash
# Copy backup to pod
kubectl cp svt-backup.tar.gz hps-svt-tracker/$(kubectl get pod -l app=svt-tracker -n hps-svt-tracker -o jsonpath='{.items[0].metadata.name}'):/tmp/

# Extract in pod
kubectl exec deployment/svt-tracker -n hps-svt-tracker -- \
  tar xzf /tmp/svt-backup.tar.gz -C /
```

## Updating the Application

```bash
# 1. Build new image
docker build -t your-registry/hps-svt-tracker:v0.2.0 ..
docker push your-registry/hps-svt-tracker:v0.2.0

# 2. Update image tag in kustomization.yaml

# 3. Apply changes
kubectl apply -k . -n hps-svt-tracker

# 4. Watch rollout
kubectl rollout status deployment/svt-tracker -n hps-svt-tracker
```

## Uninstall

```bash
# Delete all resources
kubectl delete -k . -n hps-svt-tracker

# Delete namespace (removes everything including PVC data!)
kubectl delete namespace hps-svt-tracker
```

## Troubleshooting

### Pod not starting
```bash
kubectl describe pod -l app=svt-tracker -n hps-svt-tracker
kubectl logs -l app=svt-tracker -n hps-svt-tracker --previous
```

### PVC not binding
```bash
kubectl get pvc -n hps-svt-tracker
kubectl describe pvc svt-tracker-data -n hps-svt-tracker
```

### Database errors
- Ensure only 1 replica is running (SQLite limitation)
- Check file permissions on the PVC
- Verify the data directory exists and is writable

## Architecture Notes

- **Single Replica**: SQLite doesn't support concurrent writes, so only 1 pod replica should run
- **Recreate Strategy**: Ensures old pod terminates before new one starts during updates
- **Persistent Storage**: Database and test files stored on PVC, survives pod restarts
- **Non-root User**: Application runs as UID 1000 for security
