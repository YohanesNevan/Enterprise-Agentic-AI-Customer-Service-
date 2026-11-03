"""Keep automated tests isolated from the developer's PostgreSQL instance."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./eaics_test_q.db")
os.environ.setdefault("JWT_SIGNING_KEY", "unit-test-signing-key-0123456789abcdef")
os.environ.setdefault("JWT_ISSUER", "eaics-tests")
os.environ.setdefault("JWT_AUDIENCE", "eaics-api")
os.environ.setdefault("SERVICE_TOKEN_KEYS", '{"test-worker":"unit-test-service-key-0123456789abcdef","orchestrator":"unit-test-orchestrator-key-0123456789"}')
os.environ.setdefault("SERVICE_TOKEN_SCOPES", '{"test-worker":["sla.read"],"orchestrator":["ticket.create","ticket.read","case.create","case.read","evidence.request","sla.read","handoff.initiate","conversation.read","conversation.write","knowledge.read","tool.invoke"]}')
os.environ.setdefault("SERVICE_TOKEN_ROLES", '{"test-worker":["supervisor"],"orchestrator":["ai_agent"]}')
