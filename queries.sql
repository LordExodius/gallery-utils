/* Create photo table */
CREATE TABLE IF NOT EXISTS photo (
    id INTEGER NOT NULL PRIMARY KEY,
    filename TEXT NOT NULL UNIQUE,
    thumbnail TEXT NOT NULL UNIQUE,
    date_taken TEXT,
    lens TEXT,
    focal_length TEXT,
    f_stop TEXT,
    exposure_time TEXT,
    iso TEXT,
    camera_model TEXT
);

/* Create collection table */
CREATE TABLE IF NOT EXISTS collection (
    id INTEGER NOT NULL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

/* Create photo_collection table */
CREATE TABLE IF NOT EXISTS photo_collection (
    photo_id INTEGER NOT NULL,
    collection_id INTEGER NOT NULL,
    sort_order INTEGER NOT NULL,
    FOREIGN KEY (photo_id) REFERENCES photo (id) ON DELETE CASCADE,
    FOREIGN KEY (collection_id) REFERENCES collection (id) ON DELETE CASCADE,
    PRIMARY KEY (photo_id, collection_id)
);

/* Add photo to collection */
INSERT INTO
    photo_collection
SELECT $ (PHOTO_ID), $ (COLLECTION_ID), COALESCE(
        MAX(photo_collection.sort_order) + 1, 1
    )
FROM photo_collection
WHERE
    collection_id = (
        SELECT id
        FROM collection
        WHERE
            name = ?
    ) ON CONFLICT DO NOTHING;

/* Remove photo from collection */
DELETE FROM photo_collection
WHERE
    photo_id = ?
    AND collection_id = (
        SELECT id
        FROM collection
        WHERE
            name = ?
    );

/* Select all photos in a collection by name */
SELECT *
FROM
    collection AS c
    LEFT JOIN photo_collection AS pc ON c.id = pc.collection_id
    LEFT JOIN photo AS p ON pc.photo_id = p.id
WHERE
    c.name = ?
ORDER BY pc.sort_order;