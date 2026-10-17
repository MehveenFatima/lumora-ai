from fastapi import APIRouter
from backend.app.api.routes import auth, health, documents, tutor, workspaces, quizzes, mastery, flashcards, study_plans, activities, notifications, search

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(workspaces.router)
api_router.include_router(documents.router)
api_router.include_router(tutor.router)
api_router.include_router(quizzes.router)
api_router.include_router(mastery.router)
api_router.include_router(flashcards.router)
api_router.include_router(study_plans.router)
api_router.include_router(activities.router)
api_router.include_router(notifications.router)
api_router.include_router(search.router)
