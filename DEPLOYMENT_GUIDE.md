# Railway Deployment Guide
## Fish Pond Monitoring System

### Overview
This guide will help you deploy the Fish Pond Monitoring System to Railway with separate API and Dashboard services.

### Prerequisites
- Railway account (free tier is sufficient)
- Git repository with your project code
- Railway CLI installed (optional)

### Step 1: Deploy API Service

1. **Create new project on Railway**
   - Go to railway.app and click "New Project"
   - Connect your Git repository
   - Select "Deploy from GitHub"

2. **Configure API Service**
   - Set service name: `fish-pond-api`
   - Use `railway-api.json` configuration
   - Set root directory: `/` (project root)

3. **Add PostgreSQL Database**
   - Click "+ New Service" → "Add PostgreSQL"
   - Railway will automatically provide connection variables

4. **Set Environment Variables for API**
   ```
   DB_NAME=${{RAILWAY_POSTGRES_DB_NAME}}
   DB_USER=${{RAILWAY_POSTGRES_USER}}
   DB_PASSWORD=${{RAILWAY_POSTGRES_PASSWORD}}
   DB_HOST=${{RAILWAY_POSTGRES_HOST}}
   DB_PORT=${{RAILWAY_POSTGRES_PORT}}
   JWT_SECRET_KEY=your-super-secret-jwt-key-change-this
   DEVICE_API_KEY=your-production-device-api-key-change-this
   ```

5. **Initialize Database**
   - Go to your PostgreSQL service in Railway
   - Click "Open Console" 
   - Run the contents of `database/init_railway_db.sql`

### Step 2: Deploy Dashboard Service

1. **Add New Service**
   - In your Railway project, click "New Service"
   - Select "GitHub Repo" (same repository)
   - Set service name: `fish-pond-dashboard`

2. **Configure Dashboard**
   - Use `railway-dashboard.json` configuration
   - Set environment variables:
   ```
   API_BASE_URL=https://fish-pond-api.railway.app/api
   JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production
   DASHBOARD_PORT=5001
   FLASK_ENV=production
   ```

### Step 3: Update Hardware Monitor

1. **On your Raspberry Pi**, update the `.env` file:
   ```bash
   # Copy from pi/.env.production and update the URL
   API_BASE_URL=https://fish-pond-api.railway.app/api
   DEVICE_API_KEY=your-production-device-api-key-change-this
   ```

2. **Test the connection**:
   ```bash
   python3 hardware_monitor.py
   ```

### Step 4: Verify Deployment

1. **Test API Health**:
   ```bash
   curl https://fish-pond-api.railway.app/api/health
   ```

2. **Access Dashboard**:
   - Go to `https://fish-pond-dashboard.railway.app`
   - Login with admin credentials

3. **Check Hardware Status**:
   - Hardware should now successfully connect to Railway API
   - Monitor logs for successful data transmission

### Environment Variables Reference

#### API Service Required Variables:
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` (auto-provided by Railway)
- `JWT_SECRET_KEY` (generate a secure random string)
- `DEVICE_API_KEY` (create a secure key for hardware authentication)

#### Dashboard Service Required Variables:
- `API_BASE_URL` (your Railway API URL)
- `JWT_SECRET_KEY` (must match API service)

### Troubleshooting

**Common Issues:**
1. **Database connection errors**: Verify PostgreSQL variables are set correctly
2. **CORS errors**: Ensure API_BASE_URL is correct in dashboard config
3. **Hardware connection failures**: Check API_BASE_URL and DEVICE_API_KEY on Pi

**Logs:**
- Check Railway service logs for deployment issues
- Monitor hardware monitor logs for connection problems

### Production Considerations

1. **Security**: Use strong, unique secrets for JWT_SECRET_KEY and DEVICE_API_KEY
2. **Monitoring**: Set up Railway alerts for service health
3. **Backups**: Railway automatically backs up PostgreSQL
4. **Scaling**: Both services can be scaled independently if needed

### URLs After Deployment

- **API**: `https://fish-pond-api.railway.app/api`
- **Dashboard**: `https://fish-pond-dashboard.railway.app`
- **Database**: Managed by Railway (accessible via console)

Your hardware monitor will connect to the API URL, and users will access the dashboard URL for the web interface.
