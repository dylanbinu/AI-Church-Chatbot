# Stage 1: Builder
# We use a standard Python image to build dependencies because it has all the build tools (gcc, etc.)
FROM python:3.12 as builder

WORKDIR /app
COPY requirements.txt .

# Upgrade pip and install dependencies into a specific directory
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt -t /app/dependencies

# Stage 2: Runtime
# This is the actual Lambda image (Amazon Linux 2023) which has newer SQLite!
FROM public.ecr.aws/lambda/python:3.12

# Copy installed dependencies from builder stage
COPY --from=builder /app/dependencies ${LAMBDA_TASK_ROOT}

# Copy the entire project
COPY . ${LAMBDA_TASK_ROOT}

# Set PYTHONPATH to include the code directory so imports work
ENV PYTHONPATH=${LAMBDA_TASK_ROOT}/code

# Change to code directory
WORKDIR ${LAMBDA_TASK_ROOT}/code

# Handler
CMD [ "server.handler" ]
