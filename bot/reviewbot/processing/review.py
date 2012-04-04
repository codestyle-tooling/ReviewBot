from reviewbot.processing.api import APIError, ReviewBoardServer
from reviewbot.processing.filesystem import cleanup_tempfiles, make_tempfile


class File(object):

    def __init__(self, review, filediff):
        self.review = review
        self.id = int(filediff['id'])
        self.source_file = filediff['source_file']
        self.dest_file = filediff['dest_file']

        # I'm assuming the patched file exists here.
        self.file_path = make_tempfile(
            review.server.get_patched_file(self.review.request_id,
                                           self.review.diff_revision, self.id))

        # It's also necessary to retrieve the diff data to
        # translate line numbers for commenting.
        self.diff_data = review.server.get_diff_data(self.review.request_id,
                                                     self.review.diff_revision,
                                                     self.id)

    def comment(self, line, num_lines, text, issue=False):
        data = {
            'filediff_id': self.id,
            'first_line': self._translate_line_num(line),
            'num_lines': num_lines,
            'text': text,
            'issue_opened': issue,
        }
        self.review.server.post_diff_comment(self.review.request_id,
                                             self.review.review_id, data)

    def _translate_line_num(self, line_num):
        for chunk in self.diff_data['diff_data']['chunks']:
            for row in chunk['lines']:
                if row[4] == line_num:
                    return row[0]


class Review(object):
    ship_it = False
    body_top = ""
    body_bottom = ""

    def __init__(self, server, request):
        self.server = server
        self.request_id = request['review_request_id']
        self.diff_revision = None
        if request['has_diff']:
            self.diff_revision = request['diff_revision']

        try:
            self._review_request = self.server.get_review_request(
                self.request_id)
            self._review = server.new_review(self._review_request, "", "",
                                             False, False)['review']
            self.review_id = self._review['id']
        except:
            raise

        # Get the list of files.
        # TODO: Allow arbitrary number of files (This will return max
        # of 25 at the moment).
        self._files = None
        if self.diff_revision:
            try:
                self._files = server.get_diff_files(self.request_id,
                                                    self.diff_revision)
            except:
                raise

        self.files = []
        for file in self._files['files']:
            # For now, only get files which have
            # a patched version.
            try:
                if 'patched_file' in file['links']:
                    self.files.append(File(self, file))
            except:
                print "failed on a file"
                pass

    def publish(self):
        cleanup_tempfiles()
        try:
            self.server.set_review_fields(self._review, {
                'body_top': self.body_top,
                'body_bottom': self.body_bottom,
                'ship_it': self.ship_it,
            })
            self.server.publish_review(self._review)
            return True
        except:
            return False