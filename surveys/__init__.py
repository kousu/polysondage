import os
import io, codecs, csv
import secrets
import sqlite3
from contextlib import closing

from flask import Flask
from flask import request, session, flash, g, redirect, render_template, url_for, abort, send_file


# tip from https://thepythonic.com/2019/01/18/namedtuples-easier-way/
# I'm unclear how this is different from DataClasses?
from typing import NamedTuple


class Question(NamedTuple):
    text: str
    required: bool = False


class Rating(Question):
    max: int = 5

    def __new__(cls, text: str, max: int = 5, required: bool = False):
        x = super().__new__(cls, text, required)
        x.max = max
        return x

class Text(Question):
    pass

class TextArea(Question):
    pass


class MultipleChoice(Question):
    options: list
    # options: list[str] # py3.8+
    
    # ..hack?
    # required is an optional field with a default value
    def __new__(cls, text: str, options: list, required: bool = False):
        x = super().__new__(cls, text, required)
        x.options = options
        return x

# hrm
# there does not see`

class App(Flask):
    def __init__(self):
        super().__init__(__name__, instance_relative_config=True)

        print(self.config)  # DEBUG

        self.url_map.strict_slashes = False # allow trailing slashes

        ## routes
        # Because I'm using a *regular python constructor* and not flask's almost-but-not-quite equivalent
        # suggestion of factory functions, routes can't really be written with decorator syntax:
        # the routes need to be set up on an Flask instance; not a Flask class.
        self.route("/", methods=["GET", "POST"])(self.index)
        self.route("/survey/<survey>", methods=["GET", "POST"])(self.survey)
        # uh how do i close a survey. that means... i need an admin link. dammit.
        # can i generate the admin link based on the secret key?
        # i guess i need to store this in the db too dammit

        # how should the admin links work?
        # either:
        # - you get directed to like, /survey/<survey>/admin
        # - or: you're handed a key
        # well like what's more usable? obviously the one with a copyable link, so do that
        # how would i even communicate the admin key back to you in that case anyway?
        # oh yeah
        # uh
        # hm

        # surveymonkey (and google) handle this with accounts:
        # they have a separate accounts table
        # and then a sub-table of tokens handed out per account
        # and then when you do anything you submit that token back either in a cookie or in the Authorization header

        # PUT
        # self.route("/survey/<survey>-<admin>/admin/<key>", methods=["GET", "POST"])(self.admin)

        # the logical thing would be to submit a
        # DELETE /survey/<survey>/
        # but then how do you authorize this?
        # You need to submit a cookie
        # blah i don't know maybe i can fucking solve this later and make it nice and RESTful. for now, fuck it.
        # for now: fuck deletion, i'll figure it out later.

        self.route("/survey/<survey>/export")(self.export)
        # TODO: this should really be /survey/<survey>/admin/<adminkey>/export, to keep the responses private

        #

        # the flask demo https://github.com/pallets/flask/blob/6f7762538bffe3ce9d03508ecab230bfff3e3dcd/examples/tutorial/flaskr/db.py#L9
        # makes a unique db connection *per request*
        # is it unsafe to share one across the whole app? is flask not multithreaded safe or something?
        # > sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 140644942042944 and this is thread id 140644848531200.
        # so... yes.
        # so I need to use 'g'?
        self.teardown_appcontext(self._close_db)
        db = self._db()
        if not list(db.execute("SELECT name FROM sqlite_master WHERE type='table'")):
            # empty database; initialize
            with self.open_resource("schema.sql") as sql:
                db.executescript(sql.read().decode("utf-8"))
                db.commit()

        print(
            list(db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        )  # DEBUG
        db.close()

    def _db(self):
        return sqlite3.connect("surveys.sqlite3", detect_types=sqlite3.PARSE_DECLTYPES)

    def _open_db(self):
        # sqlite3 has to be thread-local
        # so since each HTTP request is run on a different thread
        # we need to connect to the database per-request
        # flask.g is provided as a place to safely store thread-local (i.e. request-local) data
        if "db" not in g:
            g.db = self._db()
            g.db.row_factory = (
                sqlite3.Row
            )  # XXX why? this was in the flask tutorial but not explained
        return g.db

    def _close_db(self, e=None):
        if "db" in g:
            g.db.close()

    def index(self):
        if request.method == "GET":
            # display list of active surveys?
            # or do we want to keep them secret? hmm

            return render_template("index.html")
        elif request.method == "POST":
            print(request.form)

            title = request.form["title"]
            student = request.form["student"]
            instructions = request.form["instructions"]
            # TODO: input validation

            survey_id = secrets.token_urlsafe(10)  # shortish
            # TODO: handle token collisions
            admin_key = secrets.token_urlsafe()
            db = self._db()
            db.execute(
                "INSERT INTO surveys (id, title, student, instructions, admin_key) values (?, ?, ?, ?, ?)",
                (survey_id, title, student, instructions, admin_key),
            )
            db.commit()
            # TODO: use url_for() here? does it actually gain us anything?
            # TODO: how do we tell the user about what admin key they've been given
            return redirect(f"/survey/{survey_id}")

    def _questions(self, survey): # -> list[Question]:
        """
        Gather the contents of the given survey.
        """

        # For now: there's only one survey template and it's hardcoded.

        questions = [
            "Context was introduced",
            "Research goals were clearly stated",
            "Research methods were clearly described",
            "Discussion was coherent",
            "Take home messages were listed",
            "Slides were clear",
            "The presentation was adjusted to the audience",
            "The presenter spoke distinctly",
            "Presenter respected the time constraints",
            "Questions were correctly answered",
        ]
        questions = [Rating(q, required=True) for q in questions]
        questions.insert(0, Text("Your student ID", required=True))
        questions += [TextArea("Please provide constructive feedback (anonymous)")]

        # DEBUG
        #questions += [MultipleChoice("What don't you bring to a gunfight?", ["Something Borrowed", "Something Blue", "Something Old", "Something New"])] #DEBUG

        import pprint
        pprint.pprint(questions) # DEBUG

        return questions

    @staticmethod
    def _schema(questions, name='responses'):
        name = name.replace("'", "''") # avoid sql injections
        def columns():
            yield "id INTEGER PRIMARY KEY AUTOINCREMENT"
            yield "created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            for q in questions:
                column = q.text.replace("'", "''")
                datatype = ""
                if isinstance(q, (Text, TextArea)):
                    datatype = "TEXT"
                elif isinstance(q, (Rating, MultipleChoice)):
                    datatype = "INTEGER"
                yield f"'{column}'" + (" " if datatype else "") + datatype + (" NOT NULL" if q.required else "")
            yield "survey_id TEXT not null"
            yield "FOREIGN KEY (survey_id) REFERENCES survey (id)"
 
        sql = f"CREATE TABLE '{name}' (\n  " + str.join(",\n  ", columns()) + "\n);"
        return sql

    def survey(self, survey):
        db = self._db()

        if request.method == "GET":

            # print a survey
            print(survey)

            cursor = db.execute(
                "SELECT title, student, instructions FROM surveys WHERE active and id=?",
                (survey,),
            )
            S = list(cursor)
            if not S:
                return abort(404)
            elif len(S) > 1:
                # this should be impossible
                return abort(500)
            assert len(S) == 1
            (S,) = S  # extract
            S = dict(zip((d[0] for d in cursor.description), S))


            print(S) # DEBUG

            questions = self._questions(survey)
            print(self._schema(questions))

            # enumerate() numbers the questions so the template can name the responses
            questions = enumerate(questions)

            # in the future, we could store the survey questions in the database too
            # and generate the template generically from them
            return render_template(
                "survey.html",
                title=S["title"],
                student=S["student"],
                instructions=S["instructions"],
                questions=questions,

            )
        elif request.method == "POST":
            # record survey responses
            # first: validate all the required responses were given
            # if *not*, *reload* the survey with the missing questions highlighted

            questions = self._questions(survey)

            # validate the form
            for i,q in enumerate(questions):
                # 
                if q.required and not request.form.get(f"q{i}", ""):    
                    flash("Please answer all required questions.") # TODO: fr_CA
                    # TODO: test this (by removing the 'required' tags from the UI)
                    return render_template("survey.html", title=S["title"], student=S["student"], questions=questions,) 

            # Columns are named after their question text
            # Doing this makes exporting more obvious

            # But this is dangerous territory: columm names have spaces, and because but python's sqlite3 doesn't let
            # us use ? placeholders for column names we need to fall back on building up a SQL string programmatically.
            # This is SQL-injection territory.
            # the only reason this is safe is because we build the string from internal data, not user-supplied data
            columns = [q.text for q in questions]
            columns = [text.replace("'","''") for text in columns] # SQL-quote single quotes; XXX is this the only thing protecting this from SQL injection? Is it enough?
            columns = [f"'{text}'" for text in columns]
            columns += ["survey_id"]

            placeholders = ["?"]*len(columns)

            columns = str.join(", ", columns)
            placeholders = str.join(", ", placeholders)

            questions_to_indexes={q.text: i for i,q in enumerate(questions)}
            values = tuple(request.form.get(f"q{questions_to_indexes[q.text]}", None) for q in questions) + (survey,)

            sql = f"INSERT INTO responses ({columns}) values ({placeholders})"
            db.execute(sql, values)
            db.commit()

            return render_template("thanks.html")

        # is it awkward that the questions don't have good labels?
        # should they have labels? for exporting?
        
        # to run this for a different survey you would have to change survey.html, schema.sql, and the POST bit
        # that connects the two

        # maybe you could:
        # - have multiple templates in the codebase, and creation takes which to use as an optional parameter
        # - store the survey questions in the surveys table (in like..json I guess)
        #    - but then the responses table has to..also store json? which kind of defeats the entire purpose?
        # - use *multiple sqlite files*, one per survey:
        #   on creation, *compute* the schema that matches, and create that sqlite file
        # ^ okay this can be v2 ; gotta do some CSS wizardry first

    def export(self, survey):
        db = self._db()
        metadata = db.execute("SELECT * FROM surveys WHERE id=?", (survey,))
        S = list(metadata)
        if not S:
            return abort(404)
        elif len(S) > 1:
            # this should be impossible
            return abort(500)
        assert len(S) == 1
        (S,) = S  # extract
        metadata = dict(zip((d[0] for d in metadata.description), S))

        with closing(db.execute("SELECT * FROM responses")) as table:

            # TODO: instead of buffering the entire contents, write a file-like object that streams the contents
            #class CSVFile:
            #    def __init__(self, rows):
            #        self.rows = rows
            #        self._buffer = io.BytesIO()
            #        self._csv = csv.writer(codecs.getwriter('utf-8')(self._buffer))
            #    def read(self, n):
            #
            #       B = b''
            #       # try to get more content
            #       while len(B) < n:
                #       b = self._buffer.read(n - len(B))
                #       if len(b) < (n - len(B)):
                #           # overflowed our buffer; reset
                #           self._buffer.seek(0)
                #           self._buffer.truncate()
                #           
                #           # try to generate more content
                #           try:
                #               row = next(self.rows)
                #           except StopIteration:
                #               break # actually at the end of the file, so done
                #           self._csv.writerow(row)
                #
                #       B += b
                #
                #   assert len(B) <= n
                #   return B


            fd = io.BytesIO() # NB: this will be closed by send_file() # TODO: verify this.
            c = csv.writer(codecs.getwriter('utf-8')(fd))
            headers = [e[0] for e in table.description]
            c.writerow(headers)
            c.writerows(table)
            fd.seek(0)

            # TODO: compute last_modified based on the timestamps in the surveys
            return send_file(fd, mimetype="text/csv", download_name=f"{metadata['title']}-{metadata['student']}.csv", as_attachment=True)
