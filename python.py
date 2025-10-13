from flask import Flask, jsonify, render_template, request
import math
import random
import os
import pymysql
from datetime import datetime
import time
import traceback

app = Flask(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'coupon-db.c18swy2galw4.eu-west-1.rds.amazonaws.com',
    'user': 'admin', 
    'password': 'CouponApp123!',
    'database': 'coupon-db',
    'port': 3306,
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 10
}

def get_db_connection():
    """Create database connection with detailed error reporting"""
    try:
        print(f"🔗 Connecting to {DB_CONFIG['host']}...")
        connection = pymysql.connect(**DB_CONFIG)
        print("✅ Database connection successful")
        return connection
    except pymysql.MySQLError as e:
        error_code = e.args[0]
        error_message = e.args[1] if len(e.args) > 1 else str(e)
        
        print(f"❌ MySQL Error {error_code}: {error_message}")
        
        # Common error codes
        if error_code == 1045:
            print("💡 Access denied - check username/password")
        elif error_code == 1049:
            print("💡 Unknown database - check database name")
        elif error_code == 2003:
            print("💡 Cannot connect - check host/port or security groups")
        elif error_code == 1044:
            print("💡 Access denied for database - check user permissions")
            
        return None
    except Exception as e:
        print(f"❌ Unexpected connection error: {e}")
        return None

def init_database():
    """Initialize database tables"""
    print("🔄 Attempting database initialization...")
    
    connection = get_db_connection()
    if not connection:
        print("💥 Cannot initialize - no database connection")
        return False
    
    try:
        with connection.cursor() as cursor:
            # Create coupons table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS coupons (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coupon_code VARCHAR(50) NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used BOOLEAN DEFAULT FALSE,
                    used_at TIMESTAMP NULL
                )
            ''')
            print("✅ Coupons table ready")
            
            # Create usage_logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    coupon_code VARCHAR(50) NOT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45)
                )
            ''')
            print("✅ Usage_logs table ready")
            
        connection.commit()
        print("🎉 Database initialization completed successfully")
        return True
        
    except Exception as e:
        print(f"💥 Database initialization failed: {e}")
        return False
    finally:
        connection.close()

def generate_coupon_code():
    """Generate a unique coupon code"""
    return ''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=8))

@app.route('/')
def home():
    """Main page route - works even without database"""
    try:
        # Generate coupon
        coupon = generate_coupon_code()
        print(f"🎫 Generated coupon: {coupon}")
        
        # Try to store in database
        connection = get_db_connection()
        db_status = "connected" if connection else "disconnected"
        
        if connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        'INSERT IGNORE INTO coupons (coupon_code) VALUES (%s)',
                        (coupon,)
                    )
                    
                    ip_address = request.remote_addr or 'unknown'
                    cursor.execute(
                        'INSERT INTO usage_logs (coupon_code, ip_address) VALUES (%s, %s)',
                        (coupon, ip_address)
                    )
                    
                connection.commit()
                print(f"✅ Coupon stored in database")
                
            except Exception as e:
                print(f"⚠️ Failed to store coupon: {e}")
                db_status = "error"
            finally:
                connection.close()
        else:
            print("⚠️ Running without database storage")
        
        # Render template
        return render_template('index.html', 
                             coupon=coupon, 
                             db_status=db_status,
                             status="generated")
        
    except Exception as e:
        print(f"💥 Error in home route: {e}")
        # Fallback response
        return f"""
        <html>
            <head><title>Coupon Generator</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1>🎫 Coupon Generator</h1>
                <div style="background: #4CAF50; color: white; padding: 20px; border-radius: 10px; margin: 20px;">
                    <h2>Your Coupon:</h2>
                    <div style="font-size: 2em; font-weight: bold;">{coupon}</div>
                </div>
                <p>Database Status: <strong>{db_status}</strong></p>
                <button onclick="window.location.reload()" style="padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Generate New Coupon
                </button>
                <p><a href="/debug">Debug Info</a> | <a href="/health">Health Check</a></p>
            </body>
        </html>
        """

@app.route('/stats')
def stats():
    """Get coupon statistics"""
    connection = get_db_connection()
    
    if not connection:
        return jsonify({
            'total_coupons': 0,
            'used_coupons': 0,
            'today_coupons': 0,
            'available_coupons': 0,
            'database_status': 'disconnected',
            'message': 'Running in offline mode'
        })
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as total FROM coupons')
            total = cursor.fetchone()['total'] or 0
            
            cursor.execute('SELECT COUNT(*) as used FROM coupons WHERE used = TRUE')
            used = cursor.fetchone()['used'] or 0
            
            cursor.execute('SELECT COUNT(*) as today FROM coupons WHERE DATE(created_at) = CURDATE()')
            today = cursor.fetchone()['today'] or 0
            
        return jsonify({
            'total_coupons': total,
            'used_coupons': used,
            'today_coupons': today,
            'available_coupons': total - used,
            'database_status': 'connected'
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'database_status': 'error'
        }), 500
    finally:
        if connection:
            connection.close()

@app.route('/health')
def health():
    """Health check endpoint"""
    connection = get_db_connection()
    db_status = "connected" if connection else "disconnected"
    
    if connection:
        connection.close()
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat(),
        'application': 'running'
    })

@app.route('/debug')
def debug():
    """Debug information endpoint"""
    connection = get_db_connection()
    
    debug_info = {
        'application': 'running',
        'database_connection': 'connected' if connection else 'failed',
        'flask_debug': app.debug,
        'timestamp': datetime.now().isoformat(),
        'rds_endpoint': DB_CONFIG['host'],
        'database_name': DB_CONFIG['database']
    }
    
    if connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                debug_info['tables'] = [list(table.values())[0] for table in tables]
        except Exception as e:
            debug_info['database_error'] = str(e)
        finally:
            connection.close()
    
    return jsonify(debug_info)

# Initialize application
print("🚀 Starting Coupon Application...")
print(f"📊 RDS Endpoint: {DB_CONFIG['host']}")
print(f"🔑 Database: {DB_CONFIG['database']}")
print(f"👤 Username: {DB_CONFIG['user']}")

# Try to initialize database (but don't fail if it doesn't work)
init_database()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Starting Flask application on port {port}")
    app.run(host='0.0.0.0', port=port, debug=True)
