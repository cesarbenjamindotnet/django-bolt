from __future__ import annotations

import pytest
from msgspec import structs as msgspec_structs

from django_bolt.exceptions import SerializationError
from django_bolt.serializers import Serializer, field
from tests.test_models import Author, BlogPost, Comment, User, UserProfile


class BlogPostMiniSerializer(Serializer):
    id: int
    title: str


class CommentMiniSerializer(Serializer):
    id: int
    text: str


class UserMiniSerializer(Serializer):
    id: int
    username: str


class AuthorWithPlainPostsSerializer(Serializer):
    id: int
    name: str
    posts: list[BlogPostMiniSerializer] = field(default_factory=list)


class AuthorWithRequiredPostsSerializer(Serializer):
    id: int
    name: str
    posts: list[BlogPostMiniSerializer]


class BlogPostWithCommentsSerializer(Serializer):
    id: int
    title: str
    comments: list[CommentMiniSerializer] = field(
        default_factory=list
    )


class UserProfileOutputSerializer(Serializer):
    id: int
    bio: str
    user: UserMiniSerializer


class UserWithProfileBioSerializer(Serializer):
    id: int
    username: str
    profile_bio: str | None = field(source="profile.bio", default=None)


@pytest.mark.django_db
def test_from_model_plain_reverse_relation_prefetched_returns_nested_list():
    author = Author.objects.create(name="Alice", email="alice@example.com")
    BlogPost.objects.create(title="Post 1", content="One", author=author)
    BlogPost.objects.create(title="Post 2", content="Two", author=author)

    author = Author.objects.prefetch_related("posts").get(id=author.id)
    serializer = AuthorWithPlainPostsSerializer.from_model(author)

    assert len(serializer.posts) == 2
    assert all(isinstance(post, BlogPostMiniSerializer) for post in serializer.posts)
    assert {post.title for post in serializer.posts} == {"Post 1", "Post 2"}


@pytest.mark.django_db
def test_from_model_plain_reverse_relation_unprefetched_uses_default():
    author = Author.objects.create(name="Alice", email="alice@example.com")
    BlogPost.objects.create(title="Post 1", content="One", author=author)

    author = Author.objects.get(id=author.id)
    serializer = AuthorWithPlainPostsSerializer.from_model(author)

    assert serializer.posts == []


@pytest.mark.django_db
def test_from_model_required_unloaded_reverse_relation_raises_serialization_error():
    author = Author.objects.create(name="Alice", email="alice@example.com")
    BlogPost.objects.create(title="Post 1", content="One", author=author)

    author = Author.objects.get(id=author.id)

    with pytest.raises(SerializationError) as exc_info:
        AuthorWithRequiredPostsSerializer.from_model(author)

    error_message = str(exc_info.value)
    assert "posts" in error_message
    assert "prefetch_related('posts')" in error_message
    assert "afrom_model" in error_message


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_afrom_model_plain_reverse_relation_lazy_loads():
    author = await Author.objects.acreate(name="Alice", email="alice@example.com")
    await BlogPost.objects.acreate(title="Post 1", content="One", author=author)
    await BlogPost.objects.acreate(title="Post 2", content="Two", author=author)

    author = await Author.objects.aget(id=author.id)
    serializer = await AuthorWithPlainPostsSerializer.afrom_model(author)

    assert len(serializer.posts) == 2
    assert all(isinstance(post, BlogPostMiniSerializer) for post in serializer.posts)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_afrom_model_nested_many_lazy_loads_for_reverse_fk():
    author = await Author.objects.acreate(name="Alice", email="alice@example.com")
    post = await BlogPost.objects.acreate(title="Post 1", content="One", author=author)
    commenter = await Author.objects.acreate(name="Bob", email="bob@example.com")
    await Comment.objects.acreate(post=post, author=commenter, text="Nice post")

    post = await BlogPost.objects.aget(id=post.id)
    comments_serializer = await BlogPostWithCommentsSerializer.afrom_model(post)

    assert len(comments_serializer.comments) == 1
    assert isinstance(comments_serializer.comments[0], CommentMiniSerializer)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_afrom_model_lazy_loads_forward_fk_and_source_paths():
    user = await User.objects.acreate(
        username="alice",
        email="alice@example.com",
        password_hash="hash",
    )
    profile = await UserProfile.objects.acreate(user=user, bio="Hello", location="Earth")

    profile = await UserProfile.objects.aget(id=profile.id)
    profile_serializer = await UserProfileOutputSerializer.afrom_model(profile)
    user = await User.objects.aget(id=user.id)
    user_serializer = await UserWithProfileBioSerializer.afrom_model(user)

    assert isinstance(profile_serializer.user, UserMiniSerializer)
    assert profile_serializer.user.username == "alice"
    assert user_serializer.profile_bio == "Hello"


@pytest.mark.django_db
def test_from_model_unloaded_source_path_uses_default_without_querying():
    user = User.objects.create(
        username="alice",
        email="alice@example.com",
        password_hash="hash",
    )
    UserProfile.objects.create(user=user, bio="Hello", location="Earth")

    user = User.objects.get(id=user.id)
    serializer = UserWithProfileBioSerializer.from_model(user)

    assert serializer.profile_bio is None


@pytest.mark.django_db
def test_dump_fails_fast_when_manager_leaks_into_serializer_state():
    author = Author.objects.create(name="Alice", email="alice@example.com")
    serializer = AuthorWithPlainPostsSerializer(id=1, name="Alice")

    # Simulate a broken serializer state caused by bypassing from_model().
    msgspec_structs.force_setattr(serializer, "posts", author.posts)

    with pytest.raises(SerializationError) as exc_info:
        serializer.dump()

    assert "Serialize Django relations with from_model()/afrom_model()" in str(exc_info.value)
