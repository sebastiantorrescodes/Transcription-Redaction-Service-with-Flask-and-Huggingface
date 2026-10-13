from flask import Flask, request, render_template, jsonify

from redactor import MODEL_NAME, Redactor, validate_types


def create_app(redactor=None):
    app = Flask(__name__)

    # Application configuration
    app.config["MIN_SCORE"] = 0.80
    app.config["MAX_TEXT_LENGTH"] = 10000

    # Load the real model only when one wasn't supplied, otherwise use test dummy 
    if redactor is None:
        redactor = Redactor(
            min_score=app.config["MIN_SCORE"]
        )

    #Home page endpoint with template 
    @app.route("/", methods=["GET", "POST"])
    def home():
        return render_template("index.html")
    #/health endpoint 
    @app.route("/api/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "model": MODEL_NAME,
        })
   
    @app.route("/api/redact", methods=["POST"])
    def redact():
        # Require a JSON object as the request body.
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object"
            }), 400

        # Validate the transcript
        # Make sure text is string and between length 1 - 10000, if not return error
        text = data.get("text")
        max_length = app.config["MAX_TEXT_LENGTH"]

        if not isinstance(text, str) or not (
            1 <= len(text) <= max_length
        ):
            return jsonify({
                "error": f"text must be 1 to {max_length} characters"
            }), 400

        # If types is omitted, redact every supported NER type
        #An empty list is valid and means emails only
        types = data.get("types")

        # Our redactor.py file treats "None" as requesting all 4 types to be redacted
        # type objects must be list entries
        if types is not None and not isinstance(types, list):
            return jsonify({
                "error": "types must be a list"
            }), 400

        # Makes sure all type list items are valid...for instance can't have "ANIMAL" as a type item
        # Will provide a validation error if "type" is invalid 
        try:
           
            validate_types(types)
        except ValueError as error:
            return jsonify({
                "error": str(error)
            }), 400

        # Runs the redactor...Unexpected model/runtime errors are not
        # disguised as client validation errors
        result = redactor.redact(
            text,
            types=types,
        )

        # Ensure the API consistently reports the configured model
        return jsonify({
            **result,
            "model": getattr(redactor, "model_name", MODEL_NAME),
        })

    # Returns JSON formatted 404 error if routing issue with API
    # If not via API, then returns normal 404 error
    @app.errorhandler(404)
    def not_found(error):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Not found"
            }), 404

        return error

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)

