# third-party
from flask import jsonify, render_template

# sjva 공용
from framework import SystemModelSetting
from lib_metadata import MetadataServerUtil, SiteDmm, SiteJav321

from plugin import LogicModuleBase

# 패키지
from .plugin import P

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

#########################################################


class LogicJavCensoredAma(LogicModuleBase):
    db_default = {
        "jav_censored_ama_db_version": "1",
        "jav_censored_ama_order": "mgstage, jav321, r18",
        "jav_censored_ama_title_format": "[{title}] {tagline}",
        "jav_censored_ama_tag_option": "2",
        "jav_censored_ama_use_extras": "True",
        # jav321
        "jav_censored_ama_jav321_use_sjva": "False",
        "jav_censored_ama_jav321_use_proxy": "False",
        "jav_censored_ama_jav321_proxy_url": "",
        "jav_censored_ama_jav321_image_mode": "0",
        "jav_censored_ama_jav321_small_image_to_poster": "",
        "jav_censored_ama_jav321_crop_mode": "",
        "jav_censored_ama_jav321_title_format": "[{title}] {tagline}",
        "jav_censored_ama_jav321_art_count": "0",
        "jav_censored_ama_jav321_tag_option": "0",
        "jav_censored_ama_jav321_use_extras": "True",
        "jav_censored_ama_jav321_test_code": "ara-464",
    }

    site_map = {
        "dmm": SiteDmm,
        "jav321": SiteJav321,
    }

    def __init__(self, PM):
        super().__init__(PM, "setting")
        self.name = "jav_censored_ama"

    def process_menu(self, sub, req):
        arg = ModelSetting.to_dict()
        arg["sub"] = self.name
        try:
            return render_template(f"{package_name}_{self.name}_{sub}.html", arg=arg)
        except Exception:
            logger.exception("메뉴 처리 중 예외:")
            return render_template("sample.html", title=f"{package_name} - {sub}")

    def process_ajax(self, sub, req):
        try:
            if sub == "test":
                code = req.form["code"]
                call = req.form["call"]
                ModelSetting.set(f"{self.name}_{call}_test_code", code)

                data = self.search2(code, call)
                if data is None:
                    return jsonify({"ret": "no_match", "log": f"no results for '{code}' by '{call}'"})
                return jsonify({"search": data, "info": self.info(data[0]["code"])})
        except Exception as e:
            logger.exception("AJAX 요청 처리 중 예외:")
            return jsonify({"ret": "exception", "log": str(e)})

    def process_api(self, sub, req):
        if sub == "search":
            keyword = req.args.get("keyword")
            manual = req.args.get("manual") == "True"
            return jsonify(self.search(keyword, manual=manual))
        if sub == "info":
            return jsonify(self.info(req.args.get("code")))
        return None

    #########################################################

    def search2(self, keyword, site, manual=False):
        SiteClass = self.site_map.get(site, None)
        if SiteClass is None:
            return None
        sett = self.__site_settings(site)
        data = SiteClass.search(keyword, do_trans=manual, manual=manual, **sett)
        if data["ret"] == "success" and len(data["data"]) > 0:
            return data["data"]
        return None

    def search(self, keyword, manual=False):
        ret = []
        site_list = ModelSetting.get_list(f"{self.name}_order", ",")
        for idx, site in enumerate(site_list):
            data = self.search2(keyword, site, manual=manual)
            if data is not None:
                for item in data:
                    item["score"] -= idx
                ret += data
                ret = sorted(ret, key=lambda k: k["score"], reverse=True)
            if manual:
                continue
            if len(ret) > 0 and ret[0]["score"] > 95:
                break
        return ret

    def info(self, code):
        if code[1] == "T":
            site = "jav321"
        elif code[1] == "D":
            site = "dmm"
        else:
            logger.error("처리할 수 없는 코드: code=%s", code)
            return None

        ret = self.info2(code, site)
        if ret is None:
            return ret

        # lib_metadata로부터 받은 데이터를 가공
        ret["plex_is_proxy_preview"] = True  # ModelSetting.get_bool('jav_censored_plex_is_proxy_preview')
        ret["plex_is_landscape_to_art"] = True  # ModelSetting.get_bool('jav_censored_plex_landscape_to_art')
        ret["plex_art_count"] = len(ret["fanart"])

        actors = ret["actor"] or []
        for item in actors:
            # self.process_actor(item)
            item["name"] = item["originalname"]

        ret["title"] = ModelSetting.get(f"{self.name}_{site}_title_format").format(
            originaltitle=ret["originaltitle"],
            plot=ret["plot"],
            title=ret["title"],
            sorttitle=ret["sorttitle"],
            runtime=ret["runtime"],
            country=ret["country"],
            premiered=ret["premiered"],
            year=ret["year"],
            actor=actors[0].get("name", "") if actors else "",
            tagline=ret.get("tagline", ""),
        )

        if "tag" in ret:
            tag_option = ModelSetting.get(f"{self.name}_{site}_tag_option")
            if tag_option == "0":
                ret["tag"] = []
            elif tag_option == "1":
                ret["tag"] = [ret["originaltitle"].split("-")[0]]
            elif tag_option == "3":
                tmp = []
                for _ in ret.get("tag", []):
                    if _ != ret["originaltitle"].split("-")[0]:
                        tmp.append(_)
                ret["tag"] = tmp

        return ret

    def info2(self, code, site):
        use_sjva = ModelSetting.get_bool(f"{self.name}_{site}_use_sjva")
        if use_sjva:
            ret = MetadataServerUtil.get_metadata(code)
            if ret is not None:
                logger.debug("서버로부터 메타 정보 가져옴: %s", code)
                return ret

        SiteClass = self.site_map.get(site, None)
        if SiteClass is None:
            return None

        sett = self.__info_settings(site, code)
        data = SiteClass.info(code, **sett)

        if data["ret"] != "success":
            return None

        ret = data["data"]
        trans_ok = (
            SystemModelSetting.get("trans_type") == "1" and SystemModelSetting.get("trans_google_api_key").strip() != ""
        ) or SystemModelSetting.get("trans_type") in ["3", "4"]
        if use_sjva and sett["image_mode"] == "3" and trans_ok:
            MetadataServerUtil.set_metadata_jav_censored(code, ret, ret["title"].lower())
        return ret

    def __site_settings(self, site: str):
        proxy_url = None
        if ModelSetting.get_bool(f"{self.name}_{site}_use_proxy"):
            proxy_url = ModelSetting.get(f"{self.name}_{site}_proxy_url")
        return {
            "proxy_url": proxy_url,
            "image_mode": ModelSetting.get(f"{self.name}_{site}_image_mode"),
        }

    def __info_settings(self, site: str, code: str):
        sett = self.__site_settings(site)
        sett["max_arts"] = ModelSetting.get_int(f"{self.name}_{site}_art_count")
        sett["use_extras"] = ModelSetting.get_bool(f"{self.name}_{site}_use_extras")

        ps_to_poster = False
        for tmp in ModelSetting.get_list(f"{self.name}_{site}_small_image_to_poster", ","):
            if tmp in code:
                ps_to_poster = True
                break
        sett["ps_to_poster"] = ps_to_poster

        crop_mode = None
        for tmp in ModelSetting.get(f"{self.name}_{site}_crop_mode").splitlines():
            tmp = list(map(str.strip, tmp.split(":")))
            if len(tmp) != 2:
                continue
            if tmp[0] in code and tmp[1] in ["r", "l", "c"]:
                crop_mode = tmp[1]
                break
        sett["crop_mode"] = crop_mode

        return sett
