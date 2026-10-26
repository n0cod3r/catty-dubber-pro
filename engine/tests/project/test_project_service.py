from pathlib import Path

from catty_engine.project import ProjectService


def test_create_and_reload_project(
    tmp_path: Path,
) -> None:
    service = ProjectService()

    project_dir = tmp_path / "my-drama"

    created = service.create_project(
        directory=project_dir,
        name="My Drama",
    )

    loaded = service.open_project(project_dir)

    assert loaded.id == created.id
    assert loaded.name == "My Drama"
    assert loaded.schema_version == 1
    assert loaded.episodes == []


def test_import_multiple_episodes(
    tmp_path: Path,
) -> None:
    service = ProjectService()

    project_dir = tmp_path / "my-drama"

    project = service.create_project(
        directory=project_dir,
        name="My Drama",
    )

    episode_1 = tmp_path / "EP01.mp4"
    episode_2 = tmp_path / "EP02.mp4"
    episode_3 = tmp_path / "EP03.mp4"

    episode_1.touch()
    episode_2.touch()
    episode_3.touch()

    imported = service.import_episodes(
        directory=project_dir,
        project=project,
        source_paths=[
            str(episode_1),
            str(episode_2),
            str(episode_3),
        ],
    )

    assert len(imported) == 3

    assert imported[0].name == "EP01"
    assert imported[0].order == 0

    assert imported[1].name == "EP02"
    assert imported[1].order == 1

    assert imported[2].name == "EP03"
    assert imported[2].order == 2

    reloaded = service.open_project(project_dir)

    assert len(reloaded.episodes) == 3


def test_duplicate_episode_is_not_imported(
    tmp_path: Path,
) -> None:
    service = ProjectService()

    project_dir = tmp_path / "my-drama"

    project = service.create_project(
        directory=project_dir,
        name="My Drama",
    )

    episode = tmp_path / "EP01.mp4"
    episode.touch()

    service.import_episodes(
        directory=project_dir,
        project=project,
        source_paths=[str(episode)],
    )

    imported_again = service.import_episodes(
        directory=project_dir,
        project=project,
        source_paths=[str(episode)],
    )

    assert imported_again == []
    assert len(project.episodes) == 1