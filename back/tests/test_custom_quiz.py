import random
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from app.database import Base, create_database_engine
from app.models.catalog import Film, Genre, Quote
from app.repositories.catalog import SqlAlchemyQuestionRepository
from app.repositories.sessions import InMemorySessionRepository
from app.services.custom_quiz import CustomQuizPlanner
from app.services.quiz import QuizService


class MockPlanGenerator:
    namespace="mock:planner"
    def __init__(self,output:str="",error:Exception|None=None)->None:self.output=output;self.error=error;self.calls=0
    def generate(self,prompt:str)->str:
        self.calls+=1
        if self.error:raise self.error
        return self.output


def test_valid_structured_plan_is_accepted_and_cached() -> None:
    generator=MockPlanGenerator('{"difficulty":"hard","genres":["science_fiction","animation"]}')
    planner=CustomQuizPlanner(generator)
    first=planner.plan("A difficult science fiction and animation quiz"); second=planner.plan("A difficult science fiction and animation quiz")
    assert first.difficulty=="hard" and first.genres==("science_fiction","animation") and first.fallback_used is False
    assert second==first and generator.calls==1


def test_french_fallback_parser_handles_provider_failure() -> None:
    plan=CustomQuizPlanner(MockPlanGenerator(error=TimeoutError())).plan("Fais-moi un quiz difficile de science-fiction et d'animation")
    assert plan.difficulty=="hard" and plan.genres==("science_fiction","animation") and plan.fallback_used is True


def test_custom_multi_genre_session_uses_only_requested_catalog_pools(tmp_path:Path) -> None:
    engine=create_database_engine(f"sqlite:///{tmp_path/'custom.db'}"); Base.metadata.create_all(engine); factory=sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as database:
        science=Genre(name="Science Fiction"); animation=Genre(name="Animation"); horror=Genre(name="Horror")
        allowed=[]
        for index in range(5):
            allowed.append(Film(title=f"Science {index}",normalized_title=f"science {index}",release_year=2000+index,genres=[science]))
            allowed.append(Film(title=f"Animation {index}",normalized_title=f"animation {index}",release_year=2010+index,genres=[animation]))
        excluded=Film(title="Horror only",normalized_title="horror only",release_year=1999,genres=[horror])
        database.add_all([*allowed,excluded]);database.flush()
        for index,film in enumerate(allowed):database.add(Quote(text=f"Allowed quote {index}",normalized_text=f"allowed quote {index}",difficulty="hard",is_verified=True,film=film))
        database.add(Quote(text="Excluded quote",normalized_text="excluded quote",difficulty="hard",is_verified=True,film=excluded));database.commit()
    service=QuizService(SqlAlchemyQuestionRepository(factory),InMemorySessionRepository(),random.Random(2))
    created=service.create_custom_session("hard",["science_fiction","animation"]); session=service._sessions.get(created.session_id)
    assert session is not None and len(session.questions)==10
    allowed_titles={film.title for film in allowed}
    assert all(question.film_title in allowed_titles and set(question.choices).issubset(allowed_titles) for question in session.questions)
