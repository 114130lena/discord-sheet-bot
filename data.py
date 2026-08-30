import json
import os
import uuid


DATA_DIR = "data"

os.makedirs(
    DATA_DIR,
    exist_ok=True
)


def create_project():

    project_id = str(
        uuid.uuid4()
    )[:8]

    project = {
        "id": project_id,
        "teams": [],
        "image_path": None
    }

    save_project(
        project
    )

    return project


def save_project(
    project
):

    path = os.path.join(
        DATA_DIR,
        f"{project['id']}.json"
    )

    with open(
        path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            project,
            f,
            ensure_ascii=False,
            indent=2
        )


def load_project(
    project_id
):

    path = os.path.join(
        DATA_DIR,
        f"{project_id}.json"
    )

    if not os.path.exists(
        path
    ):
        return None

    with open(
        path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)


def delete_project(
    project_id
):

    path = os.path.join(
        DATA_DIR,
        f"{project_id}.json"
    )

    if os.path.exists(
        path
    ):

        os.remove(
            path
        )
