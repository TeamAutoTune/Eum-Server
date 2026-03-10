from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class BoardPerformance(Base):
    __tablename__ = "board_performances"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), nullable=False)
    artist: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reviews: Mapped[list["BoardReview"]] = relationship(
        back_populates="performance",
        cascade="all, delete-orphan",
    )


class BoardReview(Base):
    __tablename__ = "board_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    performance_id: Mapped[int] = mapped_column(ForeignKey("board_performances.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    performance: Mapped["BoardPerformance"] = relationship(back_populates="reviews")


class FreeBoardPost(Base):
    __tablename__ = "free_board_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    likes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    liked_by_user: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    comments: Mapped[list["FreeBoardComment"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        order_by="FreeBoardComment.created_at.asc()",
    )


class FreeBoardComment(Base):
    __tablename__ = "free_board_comments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("free_board_posts.id"), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    post: Mapped["FreeBoardPost"] = relationship(back_populates="comments")
