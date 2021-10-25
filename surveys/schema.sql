-- Initialize the database.
-- Drop any existing data and create empty tables.

DROP TABLE IF EXISTS surveys;
DROP TABLE IF EXISTS responses;

CREATE TABLE surveys (
  id TEXT PRIMARY KEY NOT NULL,
  title TEXT NOT NULL,
  student TEXT NOT NULL, -- the student being given feedback
  instructions TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  admin_key TEXT NOT NULL
);

CREATE TABLE responses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  'Your student ID' TEXT NOT NULL,
  'Context was introduced' INTEGER NOT NULL,
  'Research goals were clearly stated' INTEGER NOT NULL,
  'Research methods were clearly described' INTEGER NOT NULL,
  'Discussion was coherent' INTEGER NOT NULL,
  'Take home messages were listed' INTEGER NOT NULL,
  'Slides were clear' INTEGER NOT NULL,
  'The presentation was adjusted to the audience' INTEGER NOT NULL,
  'The presenter spoke distinctly' INTEGER NOT NULL,
  'Presenter respected the time constraints' INTEGER NOT NULL,
  'Questions were correctly answered' INTEGER NOT NULL,
  'Please provide constructive feedback (anonymous)' TEXT,
  survey_id TEXT not null,
  FOREIGN KEY (survey_id) REFERENCES survey (id)
);
