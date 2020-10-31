-- haha postgres lol

CREATE TABLE IF NOT EXISTS WebSession(
    session_id  CHAR(64) PRIMARY KEY NOT NULL,
    ttl         BIGINT               NOT NULL,
    points_json TEXT                 NOT NULL
);

CREATE TABLE IF NOT EXISTS Answer(
    point_json  VARCHAR(128) NOT NULL,
    answer_val  INTEGER      NOT NULL,
    answer_time BIGINT       NOT NULL
);