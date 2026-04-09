#!/bin/bash
# Run inside frontend:
# ../scripts/update_lib.sh

VERSION=2.5.0

# Build package
npm run build:lib
npm pack

# Copy package
find ../../../ab_pos_order_status/ab_pos_order_status/packages/ -name "kitchen-*.tgz" -delete
cp kitchen-screen-$VERSION.tgz ../../../ab_pos_order_status/ab_pos_order_status/packages/

# Install package
cd ../../../ab_pos_order_status/ab_pos_order_status/frontend
npm install -f ../packages/kitchen-screen-$VERSION.tgz
