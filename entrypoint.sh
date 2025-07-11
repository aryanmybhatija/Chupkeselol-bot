#!/bin/sh

# Set permissions on authorized_users.json
if [ -f "authorized_users.json" ]; then
    chmod 664 authorized_users.json
fi

# Execute the main command
exec "$@"
