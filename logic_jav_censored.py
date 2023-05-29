# third-party
from flask import jsonify, render_template

# sjva 공용
from framework import SystemModelSetting
from lib_metadata import (
    MetadataServerUtil,
    SiteAvdbs,
    SiteDmm,
    SiteHentaku,
    SiteJavbus,
    SiteMgstageDvd,
    SiteUtil,
    UtilNfo,
)

from plugin import LogicModuleBase

# 패키지
from .plugin import P

logger = P.logger
package_name = P.package_name
ModelSetting = P.ModelSetting

#########################################################


class LogicJavCensored(LogicModuleBase):
    db_default = {
        "jav_censored_db_version": "1",
        # "jav_censored_use_sjva": "False",
        "jav_censored_order": "dmm, javbus",
        #'jav_censored_plex_is_proxy_preview' : 'True',
        #'jav_censored_plex_landscape_to_art' : 'True',
        "jav_censored_actor_order": "avdbs, hentaku",
        # avdbs
        "jav_censored_avdbs_use_sjva": "False",
        "jav_censored_avdbs_use_proxy": "False",
        "jav_censored_avdbs_proxy_url": "",
        "jav_censored_avdbs_image_mode": "0",
        "jav_censored_avdbs_test_name": "",
        # hentaku
        "jav_censored_hentaku_use_sjva": "False",
        "jav_censored_hentaku_use_proxy": "False",
        "jav_censored_hentaku_proxy_url": "",
        "jav_censored_hentaku_image_mode": "0",
        "jav_censored_hentaku_test_name": "",
        # dmm
        "jav_censored_dmm_use_sjva": "False",
        "jav_censored_dmm_use_proxy": "False",
        "jav_censored_dmm_proxy_url": "",
        "jav_censored_dmm_image_mode": "0",
        "jav_censored_dmm_small_image_to_poster": "",
        "jav_censored_dmm_crop_mode": "",
        "jav_censored_dmm_title_format": "[{title}] {tagline}",
        "jav_censored_dmm_art_count": "0",
        "jav_censored_dmm_tag_option": "0",
        "jav_censored_dmm_use_extras": "True",
        "jav_censored_dmm_test_code": "ssni-900",
        # javbus
        "jav_censored_javbus_use_sjva": "False",
        "jav_censored_javbus_use_proxy": "False",
        "jav_censored_javbus_proxy_url": "",
        "jav_censored_javbus_image_mode": "0",
        "jav_censored_javbus_small_image_to_poster": "",
        "jav_censored_javbus_crop_mode": "",
        "jav_censored_javbus_title_format": "[{title}] {tagline}",
        "jav_censored_javbus_art_count": "0",
        "jav_censored_javbus_tag_option": "2",
        "jav_censored_javbus_use_extras": "True",
        "jav_censored_javbus_test_code": "abw-354",
        #
        "jav_censored_mgs_code": "abw-073",
        "jav_censored_mgs_use_proxy": "False",
        "jav_censored_mgs_proxy_url": "",
        "jav_censored_mgs_image_mode": "0",
        "jav_censored_mgs_attach_number": "",
    }

    site_map = {
        "avdbs": SiteAvdbs,
        "dmm": SiteDmm,
        "hentaku": SiteHentaku,
        "javbus": SiteJavbus,
        "mgs": SiteMgstageDvd,
    }

    def __init__(self, PM):
        super().__init__(PM, "setting")
        self.name = "jav_censored"

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
            if sub == "actor_test":
                name = req.form["name"]
                call = req.form["call"]
                ModelSetting.set(f"{self.name}_{call}_test_name", name)

                entity_actor = {"originalname": name}
                self.process_actor2(entity_actor, call)
                return jsonify(entity_actor)
        except Exception as e:
            logger.exception("AJAX 요청 처리 중 예외:")
            return jsonify({"ret": "exception", "log": str(e)})

    def process_api(self, sub, req):
        call = req.args.get("call", "")
        if sub == "search" and call in ["plex", "kodi"]:
            keyword = req.args.get("keyword").rstrip("-").strip()
            manual = req.args.get("manual") == "True"
            return jsonify(self.search(keyword, manual=manual))
        if sub == "info":
            data = self.info(req.args.get("code"))
            if call == "kodi":
                data = SiteUtil.info_to_kodi(data)
            return jsonify(data)
        return None

    def process_normal(self, sub, req):
        if sub == "nfo_download":
            code = req.args.get("code")
            call = req.args.get("call")
            if call == "dmm":
                ModelSetting.set(f"{self.name}_{call}_code", code)
                data = self.search2(code, call)
                if data:
                    info = self.info(data[0]["code"])
                    return UtilNfo.make_nfo_movie(
                        info,
                        output="file",
                        filename=info["originaltitle"].upper() + ".nfo",
                    )
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
        logger.debug("jav censored search - keyword:[%s] manual:[%s]", keyword, manual)
        ret = []
        site_list = ModelSetting.get_list(f"{self.name}_order", ",")
        for idx, site in enumerate(site_list):
            data = self.search2(keyword, site, manual=manual)
            if data is not None:
                if idx != 0:
                    for item in data:
                        item["score"] += -1
                ret += data
                ret = sorted(ret, key=lambda k: k["score"], reverse=True)
            if manual:
                continue
            if len(ret) > 0 and ret[0]["score"] > 95:
                break
        return ret

    def info(self, code):
        if code[1] == "B":
            site = "javbus"
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
            self.process_actor(item)

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
            tagline=ret["tagline"] or "",
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

    def process_actor(self, entity_actor):
        actor_site_list = ModelSetting.get_list(f"{self.name}_actor_order", ",")
        # logger.debug("actor_site_list : %s", actor_site_list)
        for site in actor_site_list:
            if self.process_actor2(entity_actor, site):
                return
        if not entity_actor.get("name", None):
            entity_actor["name"] = entity_actor["originalname"]

    def process_actor2(self, entity_actor, site) -> bool:
        originalname = entity_actor["originalname"]

        SiteClass = self.site_map.get(site, None)
        if SiteClass is None:
            return False

        code = "A" + SiteClass.site_char + originalname

        use_sjva = ModelSetting.get_bool(f"{self.name}_{site}_use_sjva")
        if use_sjva:
            data = MetadataServerUtil.get_metadata(code) or entity_actor
            name = data.get("name", None)
            thumb = data.get("thumb", "")
            if name and name != data["originalname"] and ".discordapp." in thumb:
                logger.info("서버로부터 가져온 배우 정보를 사용: %s %s", originalname, code)
                entity_actor["name"] = name
                entity_actor["name2"] = data["name2"]
                entity_actor["thumb"] = thumb
                entity_actor["site"] = data["site"]
                return True

        sett = self.__site_settings(site)
        SiteClass.get_actor_info(entity_actor, **sett)

        name = entity_actor.get("name", None)
        if not name:
            return False

        # 서버에 저장
        thumb = entity_actor.get("thumb", "")
        if use_sjva and sett["image_mode"] == "3" and name and ".discordapp." in thumb:
            MetadataServerUtil.set_metadata(code, entity_actor, originalname)
        return True

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
