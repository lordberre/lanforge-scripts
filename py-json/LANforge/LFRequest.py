# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Class holds default settings for json requests                -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
import sys

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit()


import urllib.request
import urllib.error
import urllib.parse
import json
from LANforge import LFUtils


class LFRequest:
    Default_Base_URL = "http://localhost:8080"
    No_Data = {'No Data':0}
    requested_url = ""
    post_data = No_Data
    default_headers = {
        'Accept': 'application/json'}

    def __init__(self, url, uri=None, debug_=False, die_on_error_=False):
        self.debug = debug_
        self.die_on_error = die_on_error_;

        if not url.startswith("http://") and not url.startswith("https://"):
            print("No http:// or https:// found, prepending http:// to "+url)
            url = "http://" + url
        if uri is not None:
            if not url.endswith('/') and not uri.startswith('/'):
                url += '/'
            self.requested_url = url + uri
        else:
            self.requested_url = url

        if self.requested_url.find('//'):
            protopos = self.requested_url.find("://")
            self.requested_url = self.requested_url[:protopos + 2] + self.requested_url[protopos + 2:].replace("//", "/")
        if self.debug:
            print("new LFRequest[%s]" % self.requested_url )
        if self.requested_url is None:
            raise Exception("Bad LFRequest of url[%s] uri[%s] -> None" % url, uri)

    # request first url on stack
    def formPost(self, show_error=True, debug=False, die_on_error_=False):
        if (debug == False) and (self.debug == True):
            debug = True;
        responses = []
        urlenc_data = ""
        if (debug):
            print("formPost: url: "+self.requested_url)
        if ((self.post_data != None) and (self.post_data is not self.No_Data)):
            urlenc_data = urllib.parse.urlencode(self.post_data).encode("utf-8")
            if (debug):
                print("formPost: data looks like:" + str(urlenc_data))
                print("formPost: url: "+self.requested_url)
            request = urllib.request.Request(url=self.requested_url,
                                             data=urlenc_data,
                                             headers=self.default_headers)
        else:
            request = urllib.request.Request(url=self.requested_url, headers=self.default_headers)
            print("No data for this formPost?")

        request.headers['Content-type'] = 'application/x-www-form-urlencoded'
        resp = ''
        try:
            resp = urllib.request.urlopen(request)
            responses.append(resp)
            return responses[0]
        except urllib.error.HTTPError as error:
            if (show_error):
                print("----- LFRequest::formPost:75 HTTPError: --------------------------------------------")
                print("%s: %s; URL: %s"%(error.code, error.reason, request.get_full_url()))
                LFUtils.debug_printer.pprint(error.headers)
                #print("Error: ", sys.exc_info()[0])
                #print("Request URL:", request.get_full_url())
                print("Request Content-type:", request.get_header('Content-type'))
                print("Request Accept:", request.get_header('Accept'))
                print("Request Data:")
                LFUtils.debug_printer.pprint(request.data)
                if (len(responses) > 0):
                    print("----- Response: --------------------------------------------------------")
                    LFUtils.debug_printer.pprint(responses[0].reason)

                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)
        except urllib.error.URLError as uerror:
            if (show_error):
                print("----- LFRequest::formPost:91 URLError: ---------------------------------------------")
                print("Reason: %s; URL: %s"%(uerror.reason, request.get_full_url()))
                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)

        return None

    def jsonPost(self, show_error=True, debug=False, die_on_error_=False, response_json_list_=None):
        if (debug == False) and (self.debug == True):
            debug = True
        responses = []
        if ((self.post_data != None) and (self.post_data is not self.No_Data)):
            request = urllib.request.Request(url=self.requested_url,
                                             data=json.dumps(self.post_data).encode("utf-8"),
                                             headers=self.default_headers)
        else:
            request = urllib.request.Request(url=self.requested_url, headers=self.default_headers)
            print("No data for this jsonPost?")

        request.headers['Content-type'] = 'application/json'
        try:
            resp = urllib.request.urlopen(request)
            resp_data = resp.read().decode('utf-8')
            if (debug):
                print("----- LFRequest::jsonPost:118 debug: --------------------------------------------")
                print("URL: %s :%d "% (self.requested_url, resp.status))
                LFUtils.debug_printer.pprint(resp.getheaders())
                print("----- resp_data -------------------------------------------------")
                print(resp_data)
                print("-------------------------------------------------")
            responses.append(resp)
            if response_json_list_ is not None:
                if type(response_json_list_) is not list:
                    raise ValueError("reponse_json_list_ needs to be type list")
                j = json.loads(resp_data)
                if debug:
                    print("----- LFRequest::jsonPost:129 debug: --------------------------------------------")
                    LFUtils.debug_printer.pprint(j)
                    print("-------------------------------------------------")
                response_json_list_.append(j)
            return responses[0]
        except urllib.error.HTTPError as error:
            if show_error:
                print("----- LFRequest::jsonPost:138 HTTPError: --------------------------------------------")
                print("<%s> HTTP %s: %s"%(request.get_full_url(), error.code, error.reason, ))

                print("Error: ", sys.exc_info()[0])
                print("Request URL:", request.get_full_url())
                print("Request Content-type:", request.get_header('Content-type'))
                print("Request Accept:", request.get_header('Accept'))
                print("Request Data:")
                LFUtils.debug_printer.pprint(request.data)

                if error.headers:
                    # the HTTPError is of type HTTPMessage a subclass of email.message
                    # print(type(error.keys()))
                    for headername in sorted(error.headers.keys()):
                        print ("Response %s: %s "%(headername, error.headers.get(headername)))

                if len(responses) > 0:
                    print("----- Response: --------------------------------------------------------")
                    LFUtils.debug_printer.pprint(responses[0].reason)
                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)
        except urllib.error.URLError as uerror:
            if show_error:
                print("----- LFRequest::jsonPost:162 URLError: ---------------------------------------------")
                print("Reason: %s; URL: %s"%(uerror.reason, request.get_full_url()))
                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)
        return None

    def get(self, show_error=True, debug=False, die_on_error_=False):
        if (debug == False) and (self.debug == True):
            debug = True
        if (debug):
            print("get: url: "+self.requested_url)
        myrequest = urllib.request.Request(url=self.requested_url, headers=self.default_headers)
        myresponses = []
        try:
            myresponses.append(urllib.request.urlopen(myrequest))
            return myresponses[0]
        except urllib.error.HTTPError as error:
            if show_error:
                print("----- LFRequest::get:155 HTTPError: --------------------------------------------")
                print("<%s> HTTP %s: %s"%(myrequest.get_full_url(), error.code, error.reason, ))
                if error.code != 404:
                    print("Error: ", sys.exc_info()[0])
                    print("Request URL:", myrequest.get_full_url())
                    print("Request Content-type:", myrequest.get_header('Content-type'))
                    print("Request Accept:", myrequest.get_header('Accept'))
                    print("Request Data:")
                    LFUtils.debug_printer.pprint(myrequest.data)

                if error.headers:
                    # the HTTPError is of type HTTPMessage a subclass of email.message
                    # print(type(error.keys()))
                    for headername in sorted(error.headers.keys()):
                        print ("Response %s: %s "%(headername, error.headers.get(headername)))

                if len(myresponses) > 0:
                    print("----- Response: --------------------------------------------------------")
                    LFUtils.debug_printer.pprint(myresponses[0].reason)
                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)
        except urllib.error.URLError as uerror:
            if show_error:
                print("----- LFRequest::get:177 URLError: ---------------------------------------------")
                print("Reason: %s; URL: %s"%(uerror.reason, myrequest.get_full_url()))
                print("------------------------------------------------------------------------")
                if (die_on_error_ == True) or (self.die_on_error == True):
                    exit(1)
        return None

    def getAsJson(self, show_error=True, die_on_error_=False, debug_=False):
        responses = []
        responses.append(self.get(show_error, die_on_error_=die_on_error_, debug=(debug_ or self.debug)))
        if (len(responses) < 1):
            return None
        if (responses[0] == None):
            if (show_error):
                print("No response from "+self.requested_url)
            return None
        json_data = json.loads(responses[0].read().decode('utf-8'))
        return json_data

    def addPostData(self, data):
        self.post_data = data

# ~LFRequest
